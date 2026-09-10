import { useRef, useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, useScroll, useTransform, useSpring } from 'framer-motion';
import {
  Globe,
  Satellite,
  Layers,
  Eye,
  Cpu,
  Target,
  ArrowRight,
  ChevronRight,
  ShieldCheck,
  Activity,
  Map as MapIcon,
  CheckCircle2,
  Crosshair,
  Info,
  Menu,
  X,
  Sparkles,
  Radio,
  SlidersHorizontal,
} from 'lucide-react';
import './manganex-landing.css';

// 6 Spatial layers definition for Section 01 // OUR FOUNDATION
const TERRAIN_LAYERS = [
  {
    id: 'base',
    index: '01',
    title: 'Base Terrain',
    shortLabel: 'TERRAIN',
    subtitle: 'Multispectral Elevation & Regional Morphology',
    description: 'Digital surface morphology capturing regional topography, ridgelines, and outcrop relief across Central India.',
    telemetry: 'SENTINEL-2 / DEM 30M BASELINE',
    filter: 'none',
  },
  {
    id: 'contours',
    index: '02',
    title: 'Topographic Contours',
    shortLabel: 'CONTOURS',
    subtitle: 'Regional Topographic Slope & Elevation Contours',
    description: 'Calculated topographic gradients identifying breaklines and structural geomorphology associated with mineralized horizons.',
    telemetry: 'REGIONAL CONTOUR GRADIENTS // SLOPE 0-38°',
    filter: 'contrast(1.25) hue-rotate(15deg)',
  },
  {
    id: 'spectral',
    index: '03',
    title: 'Spectral Signals',
    shortLabel: 'SPECTRAL',
    subtitle: 'SWIR / VNIR Alteration Indices',
    description: 'Band-ratio analysis isolating iron oxide, clay, and hydroxyl alteration signatures indicative of secondary mineralization.',
    telemetry: 'BAND RATIO: B4/B2 (FeOx) + B11/B8A (Clay)',
    filter: 'saturate(1.85) hue-rotate(160deg)',
  },
  {
    id: 'structural',
    index: '04',
    title: 'Structural Context',
    shortLabel: 'STRUCTURAL',
    subtitle: 'Lineament Corridors & Kinematic Buffers',
    description: 'Automated lineament extraction mapping regional shear zones, fold axes, and contact zones controlling ore localization.',
    telemetry: 'EXTRACTED LINEAMENTS: 142 SEGMENTS',
    filter: 'contrast(1.35) invert(0.15) hue-rotate(200deg)',
  },
  {
    id: 'environmental',
    index: '05',
    title: 'Environmental Context',
    shortLabel: 'ENVIRONMENTAL',
    subtitle: 'Vegetation Canopy & Environmental Baseline',
    description: 'Temporal NDVI monitoring establishing baseline canopy vigor to isolate seasonal vegetation trends from geobotanical stress.',
    telemetry: 'CANOPY HEALTH INDEX: 0.62 STABLE',
    filter: 'hue-rotate(85deg) saturate(1.4)',
  },
  {
    id: 'intelligence',
    index: '06',
    title: 'Spatial Intelligence',
    shortLabel: 'INTELLIGENCE',
    subtitle: 'Ensemble Prospectivity Screening Surface',
    description: 'Integrated multi-source screening model calculating relative prospectivity index across discrete 300m evaluation units.',
    telemetry: 'SCREENING INDEX: 0.00 – 1.00 SYNTHETIC',
    filter: 'contrast(1.3) saturate(1.6) brightness(1.05)',
  },
];

// Reserve Map layer preview definitions for Section 03
const MAP_PREVIEW_TABS = [
  {
    id: 'prospectivity',
    label: 'Prospectivity Heatmap',
    badge: 'MODEL SCREENING',
    legendTitle: 'Prospectivity Index',
    legendLow: '0.00 LOW',
    legendHigh: '1.00 HIGH',
    description: 'Ensemble machine-learning screening surface combining spectral alteration, structural lineament corridors, and topographic morphology into a unified spatial score.',
    stats: [
      { label: 'Evaluation Grid', value: '300m cells' },
      { label: 'Model Architecture', value: 'Ensemble XGBoost + RF' },
      { label: 'Validation Type', value: 'Historical Balaghat Belt' },
    ],
  },
  {
    id: 'spectral',
    label: 'Spectral Alteration',
    badge: 'REMOTE SENSING',
    legendTitle: 'FeOx Index (B4/B2)',
    legendLow: '0.12 BACKGROUND',
    legendHigh: '0.89 ANOMALY',
    description: 'Calibrated reflectance band ratios highlighting surface gossans, iron-oxide enrichment, and argillic alteration halos across the manganese corridor.',
    stats: [
      { label: 'Sensor Constellation', value: 'Sentinel-2 MSI' },
      { label: 'Spectral Resolution', value: '10m / 20m SWIR' },
      { label: 'Correction', value: 'BOA Surface Reflectance' },
    ],
  },
  {
    id: 'structural',
    label: 'Structural Lineaments',
    badge: 'GEODYNAMICS',
    legendTitle: 'Lineament Proximity Buffer',
    legendLow: '> 2.0 km',
    legendHigh: '< 300 m',
    description: 'Curated lineament vectors and fault intersections representing crustal weakness zones that historically channel hydrothermal and sedimentary enrichment.',
    stats: [
      { label: 'Vector Geometry', value: 'Shear Zones & Lineaments' },
      { label: 'Kinematic Buffer', value: '300m / 600m / 1200m' },
      { label: 'Structural Strike', value: 'ENE-WSW Sausar Trend' },
    ],
  },
  {
    id: 'ndvi',
    label: 'NDVI Time-Series',
    badge: 'TEMPORAL BASELINE',
    legendTitle: 'Normalized Vegetation Index',
    legendLow: '0.15 BARE SOIL',
    legendHigh: '0.78 DENSE CANOPY',
    description: 'Multi-temporal vegetation canopy monitoring tracking seasonal leaf-area fluctuations and identifying localized ground disturbance or geobotanical anomalies.',
    stats: [
      { label: 'Time Window', value: '8-Week Rolling Series' },
      { label: 'Index Type', value: '(NIR - Red) / (NIR + Red)' },
      { label: 'Cloud Masking', value: 'Automated QA60 Cloud Bit' },
    ],
  },
];

// Navigation menu matching the reference art direction
const NAV_LINKS = [
  { label: 'Technology', href: '#foundation' },
  { label: 'Platform', href: '#reserve-map' },
  { label: 'Reserve Map', href: '/map', isRoute: true },
  { label: 'Methodology', href: '#methodology' },
  { label: 'Impact', href: '#gps' },
  { label: 'About', href: '#evidence' },
];

export default function ManganexLandingPage() {
  const navigate = useNavigate();
  const scrollTrackRef = useRef(null);
  const satelliteNodeRef = useRef(null);
  const sensorBeamRef = useRef(null);

  const [activeLayer, setActiveLayer] = useState(TERRAIN_LAYERS[0]);
  const [activeMapTab, setActiveMapTab] = useState(MAP_PREVIEW_TABS[0]);
  const [scrolledState, setScrolledState] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    document.title = 'MANGANEX — Mapping Minerals for a Stronger Tomorrow';
  }, []);

  // Framer Motion scroll hook tied to the hero scroll track (420vh)
  const { scrollYProgress } = useScroll({
    target: scrollTrackRef,
    offset: ['start start', 'end end'],
  });

  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 90,
    damping: 24,
    restDelta: 0.001,
  });

  // Track numerical step for UI indicator
  useEffect(() => {
    return scrollYProgress.on('change', (latest) => {
      if (latest < 0.16) setScrolledState(0);
      else if (latest < 0.32) setScrolledState(1);
      else if (latest < 0.48) setScrolledState(2);
      else if (latest < 0.64) setScrolledState(3);
      else if (latest < 0.80) setScrolledState(4);
      else if (latest < 0.94) setScrolledState(5);
      else setScrolledState(6);
    });
  }, [scrollYProgress]);

  // =========================================================================
  // REALISTIC SATELLITE ORBIT LOOP (3D Inclination + Physical Earth Occlusion)
  // =========================================================================
  useEffect(() => {
    let animId;
    const startTime = performance.now();

    const updateOrbit = (now) => {
      if (!satelliteNodeRef.current) return;

      const elapsed = (now - startTime) / 1000;
      // 24 seconds per complete orbital revolution
      const orbitSpeed = (2 * Math.PI) / 24;
      // Combine autonomous time with gentle scroll influence
      const scrollInfluence = (window.scrollY || 0) * 0.0008;
      const theta = elapsed * orbitSpeed + scrollInfluence;

      // Elliptical inclined orbit parameters relative to Earth center
      const rx = 340; // horizontal semi-major axis (px)
      const ry = 130; // vertical inclination semi-minor axis (px)
      const tilt = -20 * (Math.PI / 180); // -20deg orbital inclination

      // Unrotated orbital coordinates
      const u = rx * Math.cos(theta);
      const v = ry * Math.sin(theta);

      // Rotate along inclination plane
      const x = u * Math.cos(tilt) - v * Math.sin(tilt);
      const y = u * Math.sin(tilt) + v * Math.cos(tilt);

      // Depth: depth > 0 is in front of Earth; depth < 0 is behind Earth
      const depth = Math.sin(theta);

      let opacity = 1.0;
      let zIndex = 18; // In front of Earth (Earth is at z-index: 10)
      let scale = 1.0 + 0.16 * depth;
      let brightness = 1.0 + 0.22 * depth;

      // True physical occlusion logic:
      // When the satellite travels behind Earth (depth < 0), it smoothly fades out
      // as it crosses the planetary limb and becomes COMPLETELY INVISIBLE while behind.
      if (depth < 0) {
        zIndex = 6; // Behind Earth wrapper
        scale = 0.84;
        if (depth > -0.22) {
          // Transition zone entering behind limb: fade out 1.0 -> 0.0
          opacity = (depth + 0.22) / 0.22;
        } else {
          // Completely behind Earth: invisible
          opacity = 0.0;
        }
        brightness = 0.55;
      }

      // Flight velocity vector for realistic attitude heading
      const dx = -rx * Math.sin(theta) * Math.cos(tilt) - ry * Math.cos(theta) * Math.sin(tilt);
      const dy = -rx * Math.sin(theta) * Math.sin(tilt) + ry * Math.cos(theta) * Math.cos(tilt);
      const heading = Math.atan2(dy, dx) * (180 / Math.PI);

      satelliteNodeRef.current.style.transform = `translate3d(${x}px, ${y}px, 0) rotate(${heading}deg) scale(${scale})`;
      satelliteNodeRef.current.style.zIndex = zIndex;
      satelliteNodeRef.current.style.opacity = opacity;
      satelliteNodeRef.current.style.filter = `brightness(${brightness}) drop-shadow(0 0 ${depth > 0 ? 14 : 0}px rgba(0, 240, 255, 0.45))`;

      // Sensor beam projection cone from satellite down to Earth (visible only when in front)
      if (sensorBeamRef.current) {
        const beamOpacity = depth > 0.15 ? Math.min(0.85, (depth - 0.15) * 1.5) : 0;
        sensorBeamRef.current.style.opacity = beamOpacity.toString();
      }

      animId = requestAnimationFrame(updateOrbit);
    };

    animId = requestAnimationFrame(updateOrbit);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Transform curves for the continuous cinematic camera journey:
  // 1. Earth approach, scale, and natural eastward rotation
  const earthScale = useTransform(smoothProgress, [0, 0.75], [1.0, 2.3]);
  const earthX = useTransform(smoothProgress, [0, 0.75], ['0%', '-14%']);
  const earthRotate = useTransform(smoothProgress, [0, 0.75], [0, 16]);
  // Earth stays visible through the descent, handing off seamlessly to the mountain horizon
  const earthOpacity = useTransform(smoothProgress, [0, 0.45, 0.85], [1, 1, 0]);

  // 2. Hero editorial text fades out smoothly as scrolling begins
  const heroTextOpacity = useTransform(smoothProgress, [0, 0.28], [1, 0]);
  const heroTextX = useTransform(smoothProgress, [0, 0.28], [0, -32]);
  const heroPointerEvents = useTransform(smoothProgress, (val) => (val < 0.25 ? 'auto' : 'none'));

  // 3. Mountain horizon & atmospheric cloud deck (enters early, rises up, completely prevents black gap)
  const mountainHorizonOpacity = useTransform(smoothProgress, [0.12, 0.50], [0, 1]);
  const mountainHorizonY = useTransform(smoothProgress, [0.12, 0.75], ['20%', '0%']);
  const mountainHorizonScale = useTransform(smoothProgress, [0.20, 0.90], [1.12, 1.0]);

  // 4. Contour lines & spatial signals overlaying mountain terrain
  const terrainSignalsOpacity = useTransform(smoothProgress, [0.45, 0.75], [0, 1]);

  // 5. Target acquisition telemetry overlay in mid-space
  const targetAcqOpacity = useTransform(smoothProgress, [0.20, 0.38, 0.58], [0, 1, 0]);

  // 6. Target box & reticle
  const intelligenceOpacity = useTransform(smoothProgress, [0.65, 0.88], [0, 1]);
  const reticleScale = useTransform(smoothProgress, [0.65, 0.88], [1.2, 1.0]);

  // 7. Scroll hand-off bridge prompt (connects Hero to Section 01)
  const bridgePromptOpacity = useTransform(smoothProgress, [0.75, 0.92, 1.0], [0, 1, 0.85]);

  const stepLabels = [
    '01 SPACE',
    '02 APPROACH',
    '03 TARGET ACQUISITION',
    '04 MOUNTAINS',
    '05 SPATIAL SIGNALS',
    '06 INTELLIGENCE',
    '07 FOUNDATION',
  ];

  return (
    <div className="manganex-landing" id="overview">
      {/* Persistent Global Ambient Backdrop */}
      <div className="manganex-global-backdrop" />
      <div className="manganex-global-contours" />
      <div className="manganex-global-grid" />

      {/* ====================================================================
          TOP NAVIGATION BAR (MATCHING REFERENCE ART DIRECTION)
          ==================================================================== */}
      <header className="manganex-nav">
        {/* Zone 1: Left Brand Lockup */}
        <div className="manganex-nav-left">
          <a href="#overview" className="manganex-brand-wrap" aria-label="MANGANEX Home">
            {/* Authoritative Geometric M Mineral Emblem */}
            <div className="manganex-logo-icon">
              <img
                src="/manganex_emblem.png"
                alt="MANGANEX"
                className="manganex-logo-primary"
              />
              <img
                src="/manganex_emblem_compact.svg"
                alt="MANGANEX"
                className="manganex-logo-compact"
              />
            </div>
            <div className="manganex-brand-text">
              <span className="manganex-brand-name">MANGANEX</span>
              <span className="manganex-brand-sub">Mapping Minerals for a Stronger Tomorrow</span>
            </div>
          </a>
        </div>

        {/* Zone 2: Center Curated Links */}
        <nav className="manganex-nav-center">
          <ul className="manganex-nav-links">
            {NAV_LINKS.map((link) => (
              <li key={link.label}>
                {link.isRoute ? (
                  <Link to={link.href} className="manganex-nav-link">
                    {link.label}
                  </Link>
                ) : (
                  <a href={link.href} className="manganex-nav-link">
                    {link.label}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </nav>

        {/* Zone 3: Right Action Buttons */}
        <div className="manganex-nav-right">
          <Link
            to="/map"
            className="manganex-btn-secondary"
            style={{ padding: '8px 16px', fontSize: '11px' }}
          >
            <MapIcon size={13} />
            <span>Map View</span>
          </Link>
          <button
            onClick={() => navigate('/')}
            className="manganex-btn-primary"
            style={{ padding: '9px 18px', fontSize: '12px' }}
            data-testid="nav-button-enter-manganex"
          >
            <span>Enter Manganex</span>
            <ArrowRight size={13} className="manganex-btn-arrow" />
          </button>

          {/* Mobile Menu Hamburger Toggle */}
          <button
            className="manganex-nav-mobile-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            data-testid="button-mobile-menu-toggle"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Mobile Nav Drawer */}
      {mobileMenuOpen && (
        <div className="manganex-mobile-drawer">
          <ul className="manganex-mobile-links">
            {NAV_LINKS.map((link) => (
              <li key={link.label}>
                {link.isRoute ? (
                  <Link
                    to={link.href}
                    className="manganex-mobile-link"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {link.label}
                  </Link>
                ) : (
                  <a
                    href={link.href}
                    className="manganex-mobile-link"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {link.label}
                  </a>
                )}
              </li>
            ))}
          </ul>
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <Link
              to="/map"
              className="manganex-btn-secondary"
              style={{ flex: 1, justifyContent: 'center' }}
              onClick={() => setMobileMenuOpen(false)}
            >
              <MapIcon size={14} />
              <span>Map View</span>
            </Link>
            <button
              onClick={() => {
                setMobileMenuOpen(false);
                navigate('/');
              }}
              className="manganex-btn-primary"
              style={{ flex: 1, justifyContent: 'center' }}
            >
              <span>Enter Manganex</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* ====================================================================
          HERO & SCROLL TRACK (REFERENCE COMPOSITION)
          ==================================================================== */}
      <div className="manganex-scroll-track" ref={scrollTrackRef}>
        <div className="manganex-sticky-viewport">
          {/* Deep space starfield & subtle nebula dust */}
          <div className="manganex-starfield" />
          <div className="manganex-nebula-glow" />
          <div className="manganex-space-grid" />

          {/* Main 2-Column Hero Stage */}
          <div className="manganex-hero-layout">
            {/* LEFT SIDE: Editorial Typography & Primary CTAs */}
            <motion.div
              className="manganex-hero-left"
              style={{
                opacity: heroTextOpacity,
                x: heroTextX,
                pointerEvents: heroPointerEvents,
              }}
            >
              <div className="manganex-hero-eyebrow-quote">
                PLANETARY INTELLIGENCE FOR A STRONGER TOMORROW
              </div>

              <h1 className="manganex-hero-title">
                WHAT IF THE NEXT
                <br />
                <span className="emphasis-discovery">DISCOVERY</span>
                <br />
                IS ALREADY IN SIGHT?
              </h1>

              <p className="manganex-hero-subtitle">
                MANGANEX uses spatial intelligence to turn Earth's signals into smarter exploration decisions.
              </p>

              <div className="manganex-hero-cta-group">
                <button
                  onClick={() => navigate('/')}
                  className="manganex-btn-primary"
                  data-testid="hero-button-explore-manganex"
                >
                  <span>Explore Manganex</span>
                  <ArrowRight size={15} className="manganex-btn-arrow" />
                </button>

                <Link to="/map" className="manganex-btn-secondary">
                  <span>Open Reserve Map</span>
                </Link>
              </div>

              <div className="manganex-hero-themes">
                <span>AI</span>
                <span className="sep">|</span>
                <span>SPACE TECHNOLOGY</span>
                <span className="sep">|</span>
                <span>SUSTAINABLE MINING</span>
              </div>

              <div className="manganex-scroll-prompt">
                <span className="scroll-indicator-mouse">
                  <span className="scroll-indicator-wheel" />
                </span>
                <span>SCROLL TO EXPLORE</span>
              </div>
            </motion.div>

            {/* RIGHT SIDE: Planetary & Recon Visual Stage (Earth, Orbit, Satellite) */}
            <div className="manganex-hero-right">
              {/* Earth from Space with natural eastward axial rotation */}
              <motion.div
                className="manganex-earth-wrapper"
                style={{
                  scale: earthScale,
                  x: earthX,
                  rotate: earthRotate,
                  opacity: earthOpacity,
                }}
              >
                <img
                  src="/landing/earth_space.jpg"
                  alt="Photorealistic Earth viewed from orbit with atmospheric limb lighting over India"
                  className="manganex-earth-img"
                />
                <div className="manganex-atmosphere-halo" />

                {/* Elliptical Orbital Trajectory Path */}
                <div className="manganex-orbit-stage">
                  <svg className="manganex-orbit-path-svg" viewBox="-200 -80 400 160">
                    <ellipse
                      cx="0"
                      cy="0"
                      rx="180"
                      ry="68"
                      fill="none"
                      stroke="rgba(0, 240, 255, 0.28)"
                      strokeWidth="1.2"
                      strokeDasharray="4 6"
                    />
                  </svg>

                  {/* Satellite Node with Sensor Projection Beam */}
                  <div className="manganex-satellite-node" ref={satelliteNodeRef}>
                    <img
                      src="/landing/satellite_orbit.png"
                      alt="Earth observation satellite in orbit"
                      className="manganex-satellite-img"
                    />
                    <div className="manganex-satellite-beacon" />

                    {/* Sensor beam projection cone illuminating the planet below */}
                    <div className="manganex-satellite-sensor-beam" ref={sensorBeamRef} />
                  </div>
                </div>
              </motion.div>

              {/* Vertical aerospace label on right edge matching reference */}
              <div className="manganex-hero-vertical-tag">
                FROM SPACE TO A CLEANER BRIGHTER TOMORROW
              </div>
            </div>
          </div>

          {/* Panoramic Mountain Horizon & Cloud Deck (Enters seamlessly as camera descends) */}
          <motion.div
            className="manganex-hero-mountain-layer"
            style={{
              opacity: mountainHorizonOpacity,
              y: mountainHorizonY,
              scale: mountainHorizonScale,
            }}
          >
            <img
              src="/landing/mountain_horizon.jpg"
              alt="Panoramic mountain peaks rising above sea of clouds with turquoise alpine lake"
              className="manganex-hero-mountain-img"
            />
            <div className="manganex-hero-mountain-gradient" />

            {/* Signals / Contour Lines Overlay over Mountain Horizon */}
            <motion.div
              style={{
                position: 'absolute',
                inset: 0,
                opacity: terrainSignalsOpacity,
                pointerEvents: 'none',
              }}
            >
              <svg
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.6 }}
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle cx="50%" cy="50%" r="90" fill="none" stroke="rgba(0, 240, 255, 0.4)" strokeWidth="1" strokeDasharray="3 4" />
                <circle cx="50%" cy="50%" r="180" fill="none" stroke="rgba(0, 240, 255, 0.25)" strokeWidth="1" strokeDasharray="6 6" />
                <circle cx="50%" cy="50%" r="280" fill="none" stroke="rgba(0, 240, 255, 0.15)" strokeWidth="1" />
                <line x1="50%" y1="0%" x2="50%" y2="100%" stroke="rgba(0, 240, 255, 0.15)" strokeWidth="0.8" strokeDasharray="4 6" />
                <line x1="0%" y1="50%" x2="100%" y2="50%" stroke="rgba(0, 240, 255, 0.15)" strokeWidth="0.8" strokeDasharray="4 6" />
              </svg>
            </motion.div>

            {/* Target Acquisition Reticle & Candidate Cell Box */}
            <motion.div
              className="manganex-target-reticle"
              style={{
                opacity: intelligenceOpacity,
                scale: reticleScale,
              }}
            >
              <div className="manganex-reticle-corner tl" />
              <div className="manganex-reticle-corner tr" />
              <div className="manganex-reticle-corner bl" />
              <div className="manganex-reticle-corner br" />

              <div className="manganex-target-cell-box">
                <span className="manganex-target-cell-score">0.84</span>
                <span className="manganex-target-cell-label">SCREENING INDEX</span>
                <div style={{ fontSize: '8px', color: 'var(--mg-text-muted)', marginTop: '4px', fontFamily: 'var(--mg-font-mono)' }}>
                  TARGET CELL MN-07
                </div>
              </div>
            </motion.div>
          </motion.div>

          {/* Target Acquisition Callout in Mid-Scroll */}
          <motion.div
            style={{
              position: 'absolute',
              top: '48%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              opacity: targetAcqOpacity,
              textAlign: 'center',
              pointerEvents: 'none',
              zIndex: 24,
            }}
          >
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '12px',
                background: 'rgba(5, 7, 9, 0.94)',
                border: '1px solid var(--mg-teal)',
                padding: '10px 24px',
                borderRadius: '3px',
                boxShadow: '0 0 28px rgba(0, 240, 255, 0.35)',
              }}
            >
              <Crosshair size={18} color="var(--mg-teal)" />
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontFamily: 'var(--mg-font-mono)', fontSize: '11px', color: 'var(--mg-teal)', letterSpacing: '0.14em', fontWeight: 700 }}>
                  TARGET REGION IDENTIFIED
                </div>
                <div style={{ fontFamily: 'var(--mg-font-mono)', fontSize: '9px', color: 'var(--mg-text-secondary)', letterSpacing: '0.08em' }}>
                  CENTRAL INDIA MANGANESE CORRIDOR · 21.8000° N, 80.1900° E
                </div>
              </div>
            </div>
          </motion.div>

          {/* Hero to Section 01 Transition Bridge Banner */}
          <motion.div
            className="manganex-hero-bridge-strip"
            style={{ opacity: bridgePromptOpacity }}
          >
            <Sparkles size={13} color="var(--mg-teal)" />
            <span>ORBITAL RECONNAISSANCE TO PLANETARY TERRAIN // PROCEEDING TO FOUNDATION</span>
            <ChevronRight size={13} style={{ transform: 'rotate(90deg)' }} />
          </motion.div>

          {/* Scroll Step Indicator (Right Sidebar) */}
          <div className="manganex-scroll-indicator-bar">
            {stepLabels.map((label, idx) => (
              <div key={label} className={`manganex-step-dot ${scrolledState === idx ? 'active' : ''}`}>
                <span>{label}</span>
                <span className="dot-pip" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ====================================================================
          SECTION 01 // OUR FOUNDATION — THE EARTH IS THE DATASET
          (MOUNTAIN CLOUDSCAPE + 6 HORIZONTAL LAYER CARDS)
          ==================================================================== */}
      <div className="manganex-section-env-wrap" id="foundation">
        {/* Photographic mountain clouds horizon backdrop */}
        <div className="manganex-foundation-backdrop">
          <img
            src="/landing/mountain_horizon.jpg"
            alt="Panoramic mountain peaks rising above sea of clouds with turquoise alpine lake"
            className="manganex-foundation-bg-img"
          />
          <div className="manganex-foundation-overlay" />
        </div>

        <section className="manganex-section" style={{ position: 'relative', zIndex: 6 }}>
          <div className="manganex-foundation-split">
            {/* Left Headline & Copy */}
            <div className="manganex-foundation-left">
              <span className="manganex-section-tag">01 // OUR FOUNDATION</span>
              <h2 className="manganex-section-title">THE EARTH IS THE DATASET.</h2>
              <p className="manganex-section-desc">
                Every landscape carries signals — geological structures, spectral patterns, terrain and environmental change.
                MANGANEX extracts multi-source planetary observations to reveal underlying mineralized systems.
              </p>
              <div style={{ marginTop: '24px' }}>
                <a href="#methodology" className="manganex-btn-secondary" style={{ padding: '10px 20px', fontSize: '12px' }}>
                  <span>Explore the Layers</span>
                  <ArrowRight size={13} />
                </a>
              </div>
            </div>

            {/* Right: 6 Square Thumbnail Layer Cards in Horizontal Row */}
            <div className="manganex-foundation-right">
              <div className="manganex-layer-thumbnails-row">
                {TERRAIN_LAYERS.map((layer) => {
                  const isSelected = activeLayer.id === layer.id;
                  return (
                    <div
                      key={layer.id}
                      className={`manganex-thumb-card ${isSelected ? 'active' : ''}`}
                      onClick={() => setActiveLayer(layer)}
                      data-testid={`thumb-card-${layer.id}`}
                    >
                      <div className="manganex-thumb-preview">
                        <img
                          src="/landing/terrain_geology.jpg"
                          alt={layer.title}
                          style={{ filter: layer.filter }}
                        />
                        <div className="manganex-thumb-glow" />
                        {isSelected && <span className="manganex-thumb-active-badge" />}
                      </div>
                      <span className="manganex-thumb-label">{layer.shortLabel}</span>
                    </div>
                  );
                })}
              </div>

              {/* Active Layer Details Banner */}
              <div className="manganex-active-layer-detail">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span className="manganex-active-layer-badge">
                    LAYER {activeLayer.index} // {activeLayer.title.toUpperCase()}
                  </span>
                  <span style={{ fontFamily: 'var(--mg-font-mono)', fontSize: '10px', color: 'var(--mg-text-muted)' }}>
                    {activeLayer.telemetry}
                  </span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--mg-text-secondary)', lineHeight: 1.5 }}>
                  <strong style={{ color: '#ffffff' }}>{activeLayer.subtitle}:</strong> {activeLayer.description}
                </div>
              </div>
            </div>
          </div>
        </section>
        <div className="mg-env-vertical-connector" />
      </div>

      {/* ====================================================================
          SECTION 02 // HOW IT WORKS — FROM SIGNAL TO INTELLIGENCE
          ==================================================================== */}
      <div className="manganex-section-env-wrap" id="methodology" style={{ background: '#05070a' }}>
        <div className="mg-env-contour-canvas" style={{ opacity: 0.12 }} />
        <div className="mg-env-grid-canvas" />

        <section className="manganex-section">
          <div className="manganex-section-head">
            <span className="manganex-section-tag">02 // HOW IT WORKS</span>
            <h2 className="manganex-section-title">FROM SIGNAL TO INTELLIGENCE.</h2>
            <p className="manganex-section-desc">
              We combine multiple spatial signals to generate exploration insights that help teams focus their efforts where it matters most.
            </p>
          </div>

          {/* 3 Circular Connected Step Nodes */}
          <div className="manganex-three-nodes-row">
            <div className="manganex-nodes-connect-line" />

            {/* Node 01: OBSERVE */}
            <div className="manganex-circle-node-card">
              <div className="manganex-circle-node-icon">
                <Satellite size={22} color="var(--mg-teal)" />
                <span className="manganex-circle-node-num">01</span>
              </div>
              <h3 className="manganex-circle-node-title">OBSERVE</h3>
              <p className="manganex-circle-node-desc">
                Spatial and Earth-observation signals captured across multi-sensor constellations.
              </p>
            </div>

            {/* Node 02: INTERPRET */}
            <div className="manganex-circle-node-card">
              <div className="manganex-circle-node-icon">
                <Cpu size={22} color="var(--mg-teal)" />
                <span className="manganex-circle-node-num">02</span>
              </div>
              <h3 className="manganex-circle-node-title">INTERPRET</h3>
              <p className="manganex-circle-node-desc">
                Analyze patterns, relationships and spatial context. Correlate regional fault lineaments with spectral alteration halos.
              </p>
            </div>

            {/* Node 03: PRIORITIZE */}
            <div className="manganex-circle-node-card">
              <div className="manganex-circle-node-icon">
                <Target size={22} color="var(--mg-teal)" />
                <span className="manganex-circle-node-num">03</span>
              </div>
              <h3 className="manganex-circle-node-title">PRIORITIZE</h3>
              <p className="manganex-circle-node-desc">
                Identify areas that deserve closer investigation. Generate ranked 300m candidate zones with transparent evidence.
              </p>
            </div>
          </div>
        </section>
        <div className="mg-env-vertical-connector" />
      </div>

      {/* ====================================================================
          SECTION 03 // RESERVE MAP SHOWCASE — FROM VAST TERRAIN TO FOCUSED TARGETS
          ==================================================================== */}
      <div className="manganex-section-env-wrap" id="reserve-map" style={{ background: '#070a0f' }}>
        <div className="mg-env-contour-canvas" style={{ opacity: 0.16 }} />
        <div className="mg-env-grid-canvas" />

        <section className="manganex-section">
          <div className="manganex-section-head">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '20px' }}>
              <div>
                <span className="manganex-section-tag">03 // HOW IT WORKS</span>
                <h2 className="manganex-section-title">
                  FROM VAST TERRAIN
                  <br />
                  TO FOCUSED TARGETS.
                </h2>
                <p className="manganex-section-desc">
                  Explore multiple spatial perspectives in a single intelligence environment. Screen active Central India mining concessions in seconds.
                </p>
              </div>
              <Link
                to="/map"
                className="manganex-btn-primary"
                data-testid="button-open-reserve-map-section"
              >
                <span>Open Reserve Map</span>
                <ArrowRight size={14} className="manganex-btn-arrow" />
              </Link>
            </div>
          </div>

          {/* High-Tech Reserve Map Showcase Window */}
          <div className="manganex-map-showcase">
            <div className="manganex-map-toolbar">
              <div className="manganex-map-tabs">
                {MAP_PREVIEW_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    className={`manganex-map-tab-btn ${activeMapTab.id === tab.id ? 'active' : ''}`}
                    onClick={() => setActiveMapTab(tab)}
                    data-testid={`map-tab-${tab.id}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span className="manganex-nav-badge" style={{ margin: 0, fontFamily: 'var(--mg-font-mono)', fontSize: '10px', color: 'var(--mg-teal)', padding: '3px 8px', border: '1px solid var(--mg-teal-dim)', borderRadius: '3px' }}>
                  {activeMapTab.badge}
                </span>
                <span style={{ fontFamily: 'var(--mg-font-mono)', fontSize: '11px', color: 'var(--mg-text-muted)' }}>
                  BALAGHAT SCREENING QUADRANT
                </span>
              </div>
            </div>

            <div className="manganex-map-viewport">
              <img
                src="/landing/terrain_geology.jpg"
                alt="Reserve Map geospatial visualization"
                style={{
                  filter:
                    activeMapTab.id === 'spectral'
                      ? 'saturate(2.2) hue-rotate(170deg)'
                      : activeMapTab.id === 'structural'
                      ? 'contrast(1.4) invert(0.12) hue-rotate(210deg)'
                      : activeMapTab.id === 'ndvi'
                      ? 'hue-rotate(90deg) saturate(1.5)'
                      : 'contrast(1.15) brightness(0.95)',
                }}
              />

              {/* Rainbow Prospectivity Heatmap Overlay for Default Tab */}
              {activeMapTab.id === 'prospectivity' && (
                <div className="manganex-map-prospectivity-overlay" />
              )}

              {/* Map Telemetry Legend Overlay */}
              <div className="manganex-map-hud-legend">
                <div className="manganex-map-hud-title">{activeMapTab.legendTitle}</div>
                <div className="manganex-heat-gradient-bar" />
                <div className="manganex-legend-labels">
                  <span>{activeMapTab.legendLow}</span>
                  <span>{activeMapTab.legendHigh}</span>
                </div>
              </div>
            </div>

            <div className="manganex-map-footer-bar">
              <div>
                <div style={{ fontFamily: 'var(--mg-font-display)', fontSize: '16px', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>
                  {activeMapTab.label}
                </div>
                <p style={{ fontSize: '13px', color: 'var(--mg-text-secondary)', margin: 0, lineHeight: 1.5 }}>
                  {activeMapTab.description}
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                {activeMapTab.stats.map((st) => (
                  <div key={st.label} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '6px 10px', borderRadius: '3px', border: '1px solid var(--mg-border)' }}>
                    <div style={{ fontFamily: 'var(--mg-font-mono)', fontSize: '9px', color: 'var(--mg-text-muted)', textTransform: 'uppercase' }}>
                      {st.label}
                    </div>
                    <div style={{ fontFamily: 'var(--mg-font-mono)', fontSize: '11px', color: 'var(--mg-teal)', fontWeight: 600, marginTop: '2px' }}>
                      {st.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Provenance and Demonstration Disclosure Strip */}
          <div className="manganex-disclosure-strip">
            <Info size={14} color="var(--mg-teal)" style={{ flexShrink: 0 }} />
            <span>
              <strong>Demonstration prospectivity screening:</strong> Current prototype maps utilize demonstration model indices and synthetic prospectivity surfaces to showcase spatial screening workflows. Structural lineaments represent kinematic vector features for screening demonstration.
            </span>
          </div>
        </section>
        <div className="mg-env-vertical-connector" />
      </div>

      {/* ====================================================================
          SECTION 04 // EXPLORATION GPS — YOUR EXPLORATION GPS
          ==================================================================== */}
      <div className="manganex-section-env-wrap" id="gps" style={{ background: '#05070a' }}>
        <div className="mg-env-contour-canvas" style={{ opacity: 0.12 }} />
        <div className="mg-env-grid-canvas" />

        <section className="manganex-section">
          <div className="manganex-section-head">
            <span className="manganex-section-tag">04 // EXPLORATION GPS</span>
            <h2 className="manganex-section-title">YOUR EXPLORATION GPS.</h2>
            <p className="manganex-section-desc" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--mg-teal)' }}>
              DON'T SEARCH EVERYWHERE. SEARCH SMARTER.
            </p>
            <p className="manganex-section-desc" style={{ marginTop: '8px' }}>
              MANGANEX helps exploration teams decide where to investigate first, progressively narrowing vast regional concessions into prioritized field targets.
            </p>
          </div>

          {/* 5-Step Connected Route Nodes */}
          <div className="manganex-gps-nodes-row">
            <div className="manganex-gps-connect-line" />

            <div className="manganex-gps-node-item">
              <div className="manganex-gps-node-icon">
                <ShieldCheck size={20} color="var(--mg-teal)" />
              </div>
              <div className="manganex-gps-node-name">Regional Area</div>
              <div className="manganex-gps-node-sub">BROAD ANALYSIS</div>
            </div>

            <div className="manganex-gps-node-item">
              <div className="manganex-gps-node-icon">
                <Radio size={20} color="var(--mg-teal)" />
              </div>
              <div className="manganex-gps-node-name">Spatial Signals</div>
              <div className="manganex-gps-node-sub">MULTI-LAYER DATA</div>
            </div>

            <div className="manganex-gps-node-item">
              <div className="manganex-gps-node-icon">
                <Cpu size={20} color="var(--mg-teal)" />
              </div>
              <div className="manganex-gps-node-name">Model Consensus</div>
              <div className="manganex-gps-node-sub">INTELLIGENCE</div>
            </div>

            <div className="manganex-gps-node-item featured">
              <div className="manganex-gps-node-icon">
                <Target size={20} color="#050709" />
              </div>
              <div className="manganex-gps-node-name" style={{ color: 'var(--mg-teal)' }}>Priority Zones</div>
              <div className="manganex-gps-node-sub">FOCUSED TARGETS</div>
            </div>

            <div className="manganex-gps-node-item">
              <div className="manganex-gps-node-icon">
                <Crosshair size={20} color="var(--mg-teal)" />
              </div>
              <div className="manganex-gps-node-name">Field Validation</div>
              <div className="manganex-gps-node-sub">GROUND TRUTH</div>
            </div>
          </div>
        </section>
        <div className="mg-env-vertical-connector" />
      </div>

      {/* ====================================================================
          SECTION 05 // EVIDENCE — DON'T JUST SHOW A TARGET. SHOW THE EVIDENCE.
          (3-CARD WORKSTATION LAYOUT MATCHING REFERENCE)
          ==================================================================== */}
      <div className="manganex-section-env-wrap" id="evidence" style={{ background: '#06080c' }}>
        <div className="mg-env-contour-canvas" style={{ opacity: 0.1 }} />
        <div className="mg-env-grid-canvas" />

        <section className="manganex-section">
          <div className="manganex-section-head">
            <span className="manganex-section-tag">05 // EVIDENCE</span>
            <h2 className="manganex-section-title">
              DON'T JUST SHOW A TARGET.
              <br />
              SHOW THE EVIDENCE.
            </h2>
            <p className="manganex-section-desc">
              Every target is supported by multiple spatial factors and model agreement.
            </p>
            <div style={{ marginTop: '20px' }}>
              <Link to="/map" className="manganex-btn-secondary" style={{ padding: '9px 18px', fontSize: '12px' }}>
                <span>Inspect a Target</span>
                <ArrowRight size={13} />
              </Link>
            </div>
          </div>

          {/* 3-Card Workstation Row */}
          <div className="manganex-evidence-tri-row">
            {/* Card 1: Ensemble Confidence & Target Cell */}
            <div className="manganex-evidence-panel-card">
              <div className="manganex-evidence-card-badge">
                DEMONSTRATION MODEL
              </div>
              <div className="manganex-evidence-cell-id">
                CELL #MN-BLG-300M-420
              </div>
              <div className="manganex-evidence-big-score">
                56.6%
              </div>
              <div className="manganex-evidence-score-title">
                ENSEMBLE CONFIDENCE
              </div>
              <div className="manganex-evidence-score-sub">
                2 OF 3 MODELS CONCUR · 300m CELL
              </div>
            </div>

            {/* Card 2: Contributing Spatial Factors Progress Bars */}
            <div className="manganex-evidence-panel-card">
              <div className="manganex-factors-panel-header">
                CONTRIBUTING SPATIAL FACTORS
              </div>

              <div className="manganex-factor-row">
                <span className="factor-name">FeOx Spectral Signal</span>
                <div className="factor-bar-track">
                  <div className="factor-bar-fill" style={{ width: '82%' }} />
                </div>
                <span className="factor-val">0.82</span>
              </div>

              <div className="manganex-factor-row">
                <span className="factor-name">Structural Lineament Corridor</span>
                <div className="factor-bar-track">
                  <div className="factor-bar-fill" style={{ width: '74%' }} />
                </div>
                <span className="factor-val">0.74</span>
              </div>

              <div className="manganex-factor-row">
                <span className="factor-name">Terrain Slope Profile</span>
                <div className="factor-bar-track">
                  <div className="factor-bar-fill" style={{ width: '65%' }} />
                </div>
                <span className="factor-val">0.65</span>
              </div>

              <div className="manganex-factor-row">
                <span className="factor-name">Environmental Stability</span>
                <div className="factor-bar-track">
                  <div className="factor-bar-fill" style={{ width: '91%' }} />
                </div>
                <span className="factor-val">0.91</span>
              </div>
            </div>

            {/* Card 3: Target Spatial Viewport & Thermal Scale */}
            <div className="manganex-evidence-panel-card" style={{ padding: '12px', position: 'relative', overflow: 'hidden' }}>
              <div className="manganex-target-map-crop">
                <img
                  src="/landing/terrain_geology.jpg"
                  alt="High-resolution terrain target grid"
                  className="manganex-target-crop-img"
                />
                {/* Highlighted Target Cell Reticle */}
                <div className="manganex-target-crop-box">
                  <div className="manganex-crop-crosshair" />
                </div>

                {/* Thermal Gradient Legend Strip */}
                <div className="manganex-thermal-legend">
                  <span className="thermal-label high">HIGH</span>
                  <div className="thermal-bar" />
                  <span className="thermal-label low">LOW</span>
                </div>
              </div>
            </div>
          </div>
        </section>
        <div className="mg-env-vertical-connector" />
      </div>

      {/* ====================================================================
          SECTION 06 // FROM SPACE TO THE FIELD & FINAL CTA
          (CINEMATIC MINERAL LANDSCAPE WITH AUTONOMOUS GOLDEN VEIN PULSING)
          ==================================================================== */}
      <section className="manganex-final-landscape-section" id="final-cta">
        {/* Full-bleed cinematic dark mountain terrain with golden mineral veins */}
        <div className="manganex-final-bg-wrap">
          <img
            src="/landing/final_mineral_landscape.jpg"
            alt="Dramatic dark geological mountain landscape at dusk with radiant glowing golden mineral veins"
            className="manganex-final-bg-img"
          />
          {/* Autonomous looping mist and atmospheric haze */}
          <div className="manganex-final-mist-layer" />
          {/* Autonomous pulsing mineral vein glow accent */}
          <div className="manganex-final-vein-glow" />
          <div className="manganex-final-gradient-overlay" />
        </div>

        <div className="manganex-final-content-container">
          <div className="manganex-final-tag">
            06 // FROM SPACE TO THE FIELD
          </div>

          <h2 className="manganex-final-title">
            SAME PLANET.
            <br />
            DEEPER ANSWERS.
          </h2>

          <div className="manganex-final-sub">
            MAPPING MINERALS FOR A STRONGER TOMORROW.
          </div>

          <div className="manganex-final-cta-row">
            <button
              onClick={() => navigate('/')}
              className="manganex-btn-primary"
              style={{ padding: '14px 34px', fontSize: '14px' }}
              data-testid="final-button-enter-manganex"
            >
              <span>Enter Manganex</span>
              <ArrowRight size={16} className="manganex-btn-arrow" />
            </button>

            <Link
              to="/map"
              className="manganex-btn-secondary"
              style={{ padding: '14px 28px', fontSize: '14px' }}
            >
              <MapIcon size={16} />
              <span>Open Reserve Map</span>
            </Link>
          </div>
        </div>

        {/* Bottom edge badges matching reference art direction */}
        <div className="manganex-final-bottom-bar">
          <span className="manganex-bottom-left-tag">
            NATURE · TECHNOLOGY · A BRIGHTER TOMORROW
          </span>
          <div className="manganex-bottom-right-tag">
            <span>PEOPLE</span>
            <span>RESOURCES</span>
            <span>PURPOSE</span>
          </div>
        </div>
      </section>

      {/* ====================================================================
          FOOTER
          ==================================================================== */}
      <footer className="manganex-footer">
        <div>
          <strong style={{ color: '#ffffff', letterSpacing: '0.12em' }}>MANGANEX</strong>
          <span style={{ margin: '0 8px' }}>·</span>
          <span>Mapping Minerals for a Stronger Tomorrow</span>
        </div>

        <div className="manganex-footer-right">
          <a href="#overview" className="manganex-footer-link">Overview</a>
          <a href="#foundation" className="manganex-footer-link">Technology</a>
          <a href="#reserve-map" className="manganex-footer-link">Reserve Map</a>
          <Link to="/" className="manganex-footer-link" style={{ color: 'var(--mg-teal)' }}>
            Enter Platform →
          </Link>
        </div>
      </footer>
    </div>
  );
}
