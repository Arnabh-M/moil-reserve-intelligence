import { createRoot } from 'react-dom/client';

import App from './App.jsx';

import './index.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('OreSight root element was not found');
}

createRoot(rootElement).render(<App />);
