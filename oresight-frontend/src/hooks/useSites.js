import { useEffect, useState } from 'react';
import { api } from '../api/client';

// Site-id -> name maps used to be hardcoded independently in the Simulator,
// Field Intake tabs, and Settings dropdowns -- three copies of the same
// list, silently wrong the moment /sites changes. One shared fetch instead.
export function useSites() {
  const [sites, setSites] = useState([]);
  useEffect(() => {
    let active = true;
    api.getSites().then((data) => { if (active) setSites(data); }).catch(() => {});
    return () => { active = false; };
  }, []);
  return sites;
}
