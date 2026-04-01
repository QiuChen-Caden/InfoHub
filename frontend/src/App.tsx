import { Routes, Route } from 'react-router';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import News from './pages/News';
import Runs from './pages/Runs';
import Config from './pages/Config';
import Usage from './pages/Usage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="news" element={<News />} />
        <Route path="runs" element={<Runs />} />
        <Route path="config" element={<Config />} />
        <Route path="usage" element={<Usage />} />
      </Route>
    </Routes>
  );
}
