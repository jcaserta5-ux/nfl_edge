import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './store/auth';
import Dashboard from './pages/Dashboard';
import GameDetail from './pages/GameDetail';
import PowerRankings from './pages/PowerRankings';
import InjuryTracker from './pages/InjuryTracker';
import Login from './pages/Login';
import Register from './pages/Register';
import Admin from './pages/Admin';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/"         element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/games/:id" element={<PrivateRoute><GameDetail /></PrivateRoute>} />
          <Route path="/rankings" element={<PrivateRoute><PowerRankings /></PrivateRoute>} />
          <Route path="/injuries" element={<PrivateRoute><InjuryTracker /></PrivateRoute>} />
          <Route path="/admin"    element={<PrivateRoute><Admin /></PrivateRoute>} />
          <Route path="*"         element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
