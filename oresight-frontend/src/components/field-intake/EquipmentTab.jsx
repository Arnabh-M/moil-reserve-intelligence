import { useEffect, useMemo, useRef, useState } from 'react';
import { FixedSizeList } from 'react-window';
import { Check, ChevronDown, ChevronRight, Loader2, Truck, X } from 'lucide-react';
import { api } from '../../api/client';

const ROW_HEIGHT = 42;
const GROUP_HEADER_HEIGHT = 36;
const LIST_MAX_HEIGHT = 560;
const BULK_CONCURRENCY = 6;
const GRID_TEMPLATE = '28px minmax(140px,1.6fr) minmax(85px,.8fr) minmax(160px,1.25fr) 92px minmax(150px,1.3fr)';

const timeLabel = (date) => date ? new Date(date).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—';

async function runPool(items, worker, concurrency, onSettle) {
  let cursor = 0;
  async function work() {
    while (cursor < items.length) {
      const index = cursor++;
      try {
        const value = await worker(items[index]);
        onSettle(items[index], { ok: true, value });
      } catch (error) {
        onSettle(items[index], { ok: false, error });
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) || 1 }, work));
}

function MultiSelectFilter({ label, options, selected, onChange, testId }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onDocClick = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);
  const summary = selected.length === 0 ? `All ${label.toLowerCase()}` : selected.length === 1 ? selected[0] : `${selected.length} ${label.toLowerCase()}`;
  const toggle = (value) => onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  return (
    <div className="ms-filter" ref={ref}>
      <button type="button" className="btn small" onClick={() => setOpen((o) => !o)} data-testid={testId}>
        {summary} <ChevronDown size={12} />
      </button>
      {open && (
        <div className="ms-panel card">
          <div className="ms-panel-head">
            <span>{label}</span>
            {selected.length > 0 && <button type="button" className="ms-clear" onClick={() => onChange([])}>Clear</button>}
          </div>
          <div className="ms-options">
            {options.map((option) => (
              <label className="ms-option" key={option}>
                <input type="checkbox" checked={selected.includes(option)} onChange={() => toggle(option)} />
                <span>{option}</span>
              </label>
            ))}
            {options.length === 0 && <span className="muted" style={{ fontSize: 11 }}>No options</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function EquipmentRow({ row, selected, onToggleSelect, onStatusChange, onReasonChange }) {
  return (
    <div className={`eq-row ${row.status === 'down' ? 'eq-row-down' : ''}`} style={{ display: 'grid', gridTemplateColumns: GRID_TEMPLATE, height: '100%' }} data-testid={`row-equipment-${row.id}`}>
      <span className="eq-cell eq-cell-check"><input type="checkbox" checked={selected} onChange={() => onToggleSelect(row.id)} aria-label={`Select ${row.name}`} data-testid={`checkbox-equipment-${row.id}`} /></span>
      <span className="eq-cell"><b>{row.name}</b></span>
      <span className="eq-cell muted">{row.equipment_type}</span>
      <span className="eq-cell eq-cell-status">
        <span className={`pill ${row.status === 'up' ? 'good' : 'critical'}`}>{row.status}</span>
        <select className="select" value={row.status} onChange={(event) => onStatusChange(row, event.target.value)} data-testid={`select-equipment-status-${row.id}`}>
          <option value="up">up</option><option value="down">down</option>
        </select>
      </span>
      <span className="eq-cell mono">{timeLabel(row.last_status_change)}</span>
      <span className="eq-cell">
        <input className="input" style={{ width: '100%' }} value={row.status_reason || ''} placeholder="Required if down" onChange={(event) => onReasonChange(row.id, event.target.value)} aria-label={`Reason for ${row.name}`} />
      </span>
    </div>
  );
}

function GroupHeader({ item, onToggle }) {
  return (
    <button type="button" className="eq-group-header" style={{ height: '100%' }} onClick={() => onToggle(item.siteName)} data-testid={`toggle-site-${item.siteName}`}>
      {item.expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
      <span>{item.siteName}</span>
      <span className="eq-group-count">{item.count} unit{item.count === 1 ? '' : 's'}, {item.downCount} down</span>
    </button>
  );
}

function ListRow({ index, style, data }) {
  const item = data.items[index];
  if (item.type === 'header') return <div style={style}><GroupHeader item={item} onToggle={data.onToggleGroup} /></div>;
  return <div style={style}><EquipmentRow row={item.row} selected={data.selectedIds.has(item.row.id)} onToggleSelect={data.onToggleSelect} onStatusChange={data.onStatusChange} onReasonChange={data.onReasonChange} /></div>;
}

export default function EquipmentTab({ equipmentRows, setEquipmentRows, onStatusChange, showToast, refetchAll }) {
  const [selectedSites, setSelectedSites] = useState([]);
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [expandOverrides, setExpandOverrides] = useState({});
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkState, setBulkState] = useState(null);
  const [bulkConfirmingDown, setBulkConfirmingDown] = useState(false);
  const [bulkReasonDraft, setBulkReasonDraft] = useState('');
  const lastBulkRef = useRef(null);
  const selectAllRef = useRef(null);

  useEffect(() => { const handle = setTimeout(() => setSearch(searchInput.trim().toLowerCase()), 200); return () => clearTimeout(handle); }, [searchInput]);

  const siteOptions = useMemo(() => Array.from(new Set(equipmentRows.map((row) => row.site_name))).sort(), [equipmentRows]);
  const typeOptions = useMemo(() => Array.from(new Set(equipmentRows.map((row) => row.equipment_type))).sort(), [equipmentRows]);

  const filteredRows = useMemo(() => equipmentRows.filter((row) =>
    (selectedSites.length === 0 || selectedSites.includes(row.site_name)) &&
    (selectedTypes.length === 0 || selectedTypes.includes(row.equipment_type)) &&
    (statusFilter === 'all' || row.status === statusFilter) &&
    (!search || row.name.toLowerCase().includes(search))
  ), [equipmentRows, selectedSites, selectedTypes, statusFilter, search]);

  const summary = useMemo(() => {
    const up = filteredRows.filter((row) => row.status === 'up').length;
    return { total: filteredRows.length, up, down: filteredRows.length - up };
  }, [filteredRows]);

  const autoExpand = useMemo(() => {
    const map = {};
    for (const row of equipmentRows) if (row.status === 'down') map[row.site_name] = true;
    return map;
  }, [equipmentRows]);

  const groups = useMemo(() => {
    const bySite = new Map();
    for (const row of filteredRows) {
      if (!bySite.has(row.site_name)) bySite.set(row.site_name, []);
      bySite.get(row.site_name).push(row);
    }
    return Array.from(bySite.entries()).sort(([a], [b]) => a.localeCompare(b)).map(([siteName, rows]) => {
      const sorted = [...rows].sort((a, b) => {
        if (a.status !== b.status) return a.status === 'down' ? -1 : 1;
        if (a.equipment_type !== b.equipment_type) return a.equipment_type.localeCompare(b.equipment_type);
        return a.name.localeCompare(b.name);
      });
      return { siteName, rows: sorted, downCount: sorted.filter((row) => row.status === 'down').length };
    });
  }, [filteredRows]);

  const flatItems = useMemo(() => {
    const items = [];
    for (const group of groups) {
      const expanded = expandOverrides[group.siteName] ?? Boolean(autoExpand[group.siteName]);
      items.push({ type: 'header', key: `h-${group.siteName}`, siteName: group.siteName, count: group.rows.length, downCount: group.downCount, expanded });
      if (expanded) for (const row of group.rows) items.push({ type: 'row', key: `r-${row.id}`, row });
    }
    return items;
  }, [groups, expandOverrides, autoExpand]);

  const toggleGroup = (siteName) => setExpandOverrides((prev) => ({ ...prev, [siteName]: !(prev[siteName] ?? Boolean(autoExpand[siteName])) }));

  const visibleIds = useMemo(() => filteredRows.map((row) => row.id), [filteredRows]);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const someVisibleSelected = visibleIds.some((id) => selectedIds.has(id));
  useEffect(() => { if (selectAllRef.current) selectAllRef.current.indeterminate = someVisibleSelected && !allVisibleSelected; }, [someVisibleSelected, allVisibleSelected]);

  const toggleSelectAllVisible = () => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (allVisibleSelected) visibleIds.forEach((id) => next.delete(id));
    else visibleIds.forEach((id) => next.add(id));
    return next;
  });
  const toggleRowSelected = (id) => setSelectedIds((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const onReasonChange = (id, value) => setEquipmentRows((rows) => rows.map((row) => row.id === id ? { ...row, status_reason: value } : row));

  const runBulkUpdate = async (targetStatus, reasonText, idsOverride) => {
    const ids = idsOverride || Array.from(selectedIds);
    if (!ids.length) return;
    if (targetStatus === 'down' && !reasonText.trim()) { showToast('Validation: reason is required when marking selected equipment down.'); return; }
    const items = equipmentRows.filter((row) => ids.includes(row.id));
    lastBulkRef.current = { status: targetStatus, reason: reasonText };
    const succeeded = [];
    const failed = [];
    setBulkState({ total: items.length, done: 0, succeeded, failed, running: true });
    await runPool(items, (item) => api.updateEquipmentStatus(item.id, {
      status: targetStatus,
      status_reason: targetStatus === 'up' ? (item.status_reason || 'Returned to service from field intake') : reasonText,
    }), BULK_CONCURRENCY, (item, result) => {
      if (result.ok) { succeeded.push(item.id); setEquipmentRows((rows) => rows.map((row) => row.id === item.id ? result.value : row)); }
      else failed.push({ id: item.id, name: item.name, error: result.error });
      setBulkState({ total: items.length, done: succeeded.length + failed.length, succeeded: [...succeeded], failed: [...failed], running: true });
    });
    setBulkState({ total: items.length, done: items.length, succeeded: [...succeeded], failed: [...failed], running: false });
    showToast(`${succeeded.length} updated successfully, ${failed.length} failed`);
    await refetchAll?.();
    setBulkConfirmingDown(false);
    setBulkReasonDraft('');
    if (failed.length === 0) { setSelectedIds(new Set()); setBulkState(null); }
  };

  const retryFailed = () => {
    if (!bulkState?.failed?.length || !lastBulkRef.current) return;
    runBulkUpdate(lastBulkRef.current.status, lastBulkRef.current.reason, bulkState.failed.map((f) => f.id));
  };

  const listHeight = Math.min(flatItems.length * ROW_HEIGHT, LIST_MAX_HEIGHT) || ROW_HEIGHT;
  const itemSize = () => ROW_HEIGHT;

  return (
    <section className="card section-card">
      <div className="card-head">
        <div><div className="card-title">Equipment status</div><div className="card-kicker">contract enum: up / down · reason is required when marking down</div></div>
        <Truck size={17} />
      </div>

      <div className="eq-toolbar">
        <div className="filter-row" style={{ marginBottom: 10 }}>
          <MultiSelectFilter label="Sites" options={siteOptions} selected={selectedSites} onChange={setSelectedSites} testId="filter-equipment-site" />
          <MultiSelectFilter label="Types" options={typeOptions} selected={selectedTypes} onChange={setSelectedTypes} testId="filter-equipment-type" />
          <div className="segmented" role="group" aria-label="Filter by status">
            {['all', 'down', 'up'].map((value) => (
              <button key={value} type="button" className={statusFilter === value ? 'active' : ''} onClick={() => setStatusFilter(value)} data-testid={`filter-status-${value}`}>
                {value === 'all' ? 'All' : value === 'down' ? 'Down only' : 'Up only'}
              </button>
            ))}
          </div>
          <input className="input" style={{ minWidth: 200 }} value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search equipment by name" aria-label="Search equipment" data-testid="input-equipment-search" />
        </div>
        <div className="eq-summary" data-testid="equipment-summary">
          <b>{summary.total.toLocaleString()}</b> units · <b>{summary.up.toLocaleString()}</b> up · <b>{summary.down.toLocaleString()}</b> down
        </div>
      </div>

      {flatItems.length === 0 ? (
        <div className="empty"><Truck size={25} /><strong>No equipment matches these filters</strong><div className="subhead">Clear a filter or broaden the search to see more units.</div></div>
      ) : (
        <div className="eq-table">
          <div className="eq-grid-header" style={{ display: 'grid', gridTemplateColumns: GRID_TEMPLATE, height: GROUP_HEADER_HEIGHT }}>
            <span className="eq-cell eq-cell-check">
              <input type="checkbox" ref={selectAllRef} checked={allVisibleSelected} onChange={toggleSelectAllVisible} aria-label="Select all visible equipment" data-testid="checkbox-select-all-visible" />
            </span>
            <span>Equipment</span><span>Type</span><span>Status</span><span>Last changed</span><span>Reason</span>
          </div>
          <FixedSizeList
            height={listHeight}
            width="100%"
            itemCount={flatItems.length}
            itemSize={itemSize()}
            itemKey={(index) => flatItems[index].key}
            itemData={{ items: flatItems, selectedIds, onToggleSelect: toggleRowSelected, onToggleGroup: toggleGroup, onStatusChange, onReasonChange }}
          >
            {ListRow}
          </FixedSizeList>
        </div>
      )}

      {selectedIds.size > 0 && (
        <div className="bulk-bar" data-testid="bulk-action-bar">
          {!bulkState && (
            <>
              <span><b>{selectedIds.size}</b> selected</span>
              <button className="btn small" onClick={() => runBulkUpdate('up', '')} data-testid="button-bulk-up">Mark selected Up</button>
              {!bulkConfirmingDown ? (
                <button className="btn small" onClick={() => setBulkConfirmingDown(true)} data-testid="button-bulk-down">Mark selected Down</button>
              ) : (
                <>
                  <input className="input" style={{ minWidth: 200 }} placeholder="Reason (required)" value={bulkReasonDraft} onChange={(event) => setBulkReasonDraft(event.target.value)} data-testid="input-bulk-reason" />
                  <button className="btn small primary" onClick={() => runBulkUpdate('down', bulkReasonDraft)} data-testid="button-bulk-down-confirm">Confirm</button>
                  <button className="btn small ghost" onClick={() => { setBulkConfirmingDown(false); setBulkReasonDraft(''); }} data-testid="button-bulk-down-cancel">Cancel</button>
                </>
              )}
              <button className="btn small ghost" style={{ marginLeft: 'auto' }} onClick={() => { setSelectedIds(new Set()); setBulkConfirmingDown(false); setBulkReasonDraft(''); }} data-testid="button-bulk-clear"><X size={12} /> Clear</button>
            </>
          )}
          {bulkState && (
            <div className="bulk-progress">
              {bulkState.running ? <Loader2 size={13} className="spin" /> : <Check size={13} />}
              <span>{bulkState.running ? `Updating ${bulkState.done} of ${bulkState.total}…` : `${bulkState.succeeded.length} updated successfully, ${bulkState.failed.length} failed`}</span>
              <span>✓ {bulkState.succeeded.length} done</span>
              {bulkState.running && <span>⏳ {bulkState.total - bulkState.done} in progress</span>}
              {bulkState.failed.length > 0 && <span>⚠ {bulkState.failed.length} failed</span>}
              {!bulkState.running && bulkState.failed.length > 0 && (
                <>
                  <span className="bulk-fail-names muted">{bulkState.failed.map((f) => f.name).join(', ')}</span>
                  <button className="btn small" onClick={retryFailed} data-testid="button-bulk-retry">Retry failed</button>
                  <button className="btn small ghost" onClick={() => { setBulkState(null); setSelectedIds(new Set()); }} data-testid="button-bulk-dismiss">Dismiss</button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
