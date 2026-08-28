import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppStateProvider } from './state/AppState';
import Landing from './screens/Landing';
import Report from './screens/Report';
import Track from './screens/Track';
import Signup from './screens/Signup';
import Board from './screens/Board';
import Mission from './screens/Mission';
import Login from './screens/Login';
import Dashboard from './screens/Dashboard';
import Matching from './screens/Matching';
import Recovery from './screens/Recovery';
import Offline from './screens/Offline';
import DemoIndex from './screens/DemoIndex';

export default function App() {
  return (
    <AppStateProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/reportar" element={<Report />} />
          <Route path="/seguimiento/:id" element={<Track />} />
          <Route path="/registro" element={<Signup />} />
          <Route path="/voluntario/misiones" element={<Board />} />
          <Route path="/voluntario/mapa/:id" element={<Mission />} />
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/matching/:id" element={<Matching />} />
          <Route path="/recuperacion/:id" element={<Recovery />} />
          <Route path="/offline" element={<Offline />} />
          <Route path="/demo" element={<DemoIndex />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppStateProvider>
  );
}
