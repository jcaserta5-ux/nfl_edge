import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuthStore } from '../store/auth';

export default function Register() {
  const [form, setForm] = useState({ email: '', username: '', password: '', invite_code: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await authApi.register(form.email, form.username, form.password, form.invite_code);
      login(res.data.access_token, form.username);
      navigate('/');
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Registration failed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🏈</div>
          <h1 className="text-2xl font-black text-white">Create Account</h1>
          <p className="text-gray-400 text-sm mt-1">You'll need an invite code to join</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-gray-900 rounded-2xl border border-gray-800 p-6 space-y-4">
          {[
            { label: 'Email', key: 'email', type: 'email', placeholder: 'you@example.com' },
            { label: 'Username', key: 'username', type: 'text', placeholder: 'sharpbettor99' },
            { label: 'Password', key: 'password', type: 'password', placeholder: '••••••••' },
            { label: 'Invite Code', key: 'invite_code', type: 'text', placeholder: 'aBcDeFgHiJkLmNoP' },
          ].map(({ label, key, type, placeholder }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
              <input
                type={type} value={(form as any)[key]} onChange={set(key)} required
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 focus:ring-2 focus:ring-emerald-500 outline-none text-sm"
                placeholder={placeholder}
              />
            </div>
          ))}
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button
            type="submit" disabled={loading}
            className="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-bold py-2.5 rounded-lg text-sm transition-colors"
          >
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
          <p className="text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="text-emerald-400 hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
