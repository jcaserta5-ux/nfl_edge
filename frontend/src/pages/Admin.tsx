import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuthStore } from '../store/auth';
import { Link } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, Copy, Check, Shield, UserCheck } from 'lucide-react';

// ── API helpers ───────────────────────────────────────────────────────────────

const adminApi = {
  listInvites:      () => api.get('/admin/invites').then(r => r.data),
  generateInvites:  (count: number) => api.post('/admin/invites/generate', { count }).then(r => r.data),
  revokeInvite:     (code: string) => api.delete(`/admin/invites/${code}`).then(r => r.data),
  listUsers:        () => api.get('/admin/users').then(r => r.data),
  toggleAdmin:      (id: number) => api.patch(`/admin/users/${id}/admin`).then(r => r.data),
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function Admin() {
  const { username } = useAuthStore();
  const qc = useQueryClient();
  const [count, setCount] = useState(5);
  const [tab, setTab] = useState<'invites' | 'users'>('invites');
  const [copied, setCopied] = useState<string | null>(null);

  const { data: inviteData } = useQuery({ queryKey: ['admin-invites'], queryFn: adminApi.listInvites });
  const { data: userData }   = useQuery({ queryKey: ['admin-users'],   queryFn: adminApi.listUsers });

  const generateMut = useMutation({
    mutationFn: (n: number) => adminApi.generateInvites(n),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-invites'] }),
  });

  const revokeMut = useMutation({
    mutationFn: (code: string) => adminApi.revokeInvite(code),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-invites'] }),
  });

  const toggleAdminMut = useMutation({
    mutationFn: (id: number) => adminApi.toggleAdmin(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(code);
    setTimeout(() => setCopied(null), 2000);
  };

  const invites = inviteData?.invites ?? [];
  const users   = userData?.users ?? [];
  const activeInvites = invites.filter((i: any) => i.is_active && !i.used_at);
  const usedInvites   = invites.filter((i: any) => i.used_at);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-4">
        <Link to="/" className="text-gray-400 hover:text-white">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <Shield className="w-5 h-5 text-emerald-400" />
        <h1 className="text-lg font-bold">Admin Panel</h1>
        <span className="text-sm text-gray-500 ml-auto">Logged in as {username}</span>
      </header>

      <div className="max-w-4xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(['invites', 'users'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t
                  ? 'bg-emerald-500 text-black'
                  : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {t === 'invites' ? `Invite Codes (${activeInvites.length} active)` : `Users (${users.length})`}
            </button>
          ))}
        </div>

        {/* Invites tab */}
        {tab === 'invites' && (
          <div className="space-y-6">
            {/* Generate */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <h2 className="font-semibold mb-4 text-gray-200">Generate New Codes</h2>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={1} max={50}
                  value={count}
                  onChange={e => setCount(Number(e.target.value))}
                  className="w-20 bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <span className="text-gray-400 text-sm">invite codes</span>
                <button
                  onClick={() => generateMut.mutate(count)}
                  disabled={generateMut.isPending}
                  className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  {generateMut.isPending ? 'Generating…' : 'Generate'}
                </button>
              </div>

              {/* Newly generated */}
              {generateMut.data?.generated?.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs text-emerald-400 font-semibold mb-2">✅ New codes — share these with friends:</p>
                  {generateMut.data.generated.map((inv: any) => (
                    <div key={inv.code} className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2">
                      <code className="text-emerald-300 font-mono text-sm flex-1">{inv.code}</code>
                      <button onClick={() => copyCode(inv.code)} className="text-emerald-400 hover:text-emerald-300">
                        {copied === inv.code ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Active codes */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <h2 className="font-semibold mb-4 text-gray-200">Active Invite Codes ({activeInvites.length})</h2>
              {activeInvites.length === 0 ? (
                <p className="text-gray-500 text-sm">No active codes. Generate some above.</p>
              ) : (
                <div className="space-y-2">
                  {activeInvites.map((inv: any) => (
                    <div key={inv.code} className="flex items-center gap-3 bg-gray-800 rounded-lg px-3 py-2.5">
                      <code className="text-white font-mono text-sm flex-1">{inv.code}</code>
                      {inv.expires_at && (
                        <span className="text-xs text-gray-500">
                          expires {new Date(inv.expires_at).toLocaleDateString()}
                        </span>
                      )}
                      <button onClick={() => copyCode(inv.code)} className="text-gray-400 hover:text-white">
                        {copied === inv.code ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => revokeMut.mutate(inv.code)}
                        disabled={revokeMut.isPending}
                        className="text-red-400 hover:text-red-300 disabled:opacity-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Used codes */}
            {usedInvites.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
                <h2 className="font-semibold mb-4 text-gray-400">Used Codes ({usedInvites.length})</h2>
                <div className="space-y-2">
                  {usedInvites.map((inv: any) => (
                    <div key={inv.code} className="flex items-center gap-3 bg-gray-800/50 rounded-lg px-3 py-2 opacity-60">
                      <code className="text-gray-500 font-mono text-sm flex-1 line-through">{inv.code}</code>
                      <span className="text-xs text-gray-600">
                        used {inv.used_at ? new Date(inv.used_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Users tab */}
        {tab === 'users' && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left">
                  <th className="px-4 py-3 text-gray-400 font-medium">Username</th>
                  <th className="px-4 py-3 text-gray-400 font-medium">Email</th>
                  <th className="px-4 py-3 text-gray-400 font-medium">Joined</th>
                  <th className="px-4 py-3 text-gray-400 font-medium">Last Login</th>
                  <th className="px-4 py-3 text-gray-400 font-medium">Admin</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user: any) => (
                  <tr key={user.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-3 font-medium">{user.username}</td>
                    <td className="px-4 py-3 text-gray-400">{user.email}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleAdminMut.mutate(user.id)}
                        disabled={toggleAdminMut.isPending}
                        className={`flex items-center gap-1.5 text-xs font-semibold px-2 py-1 rounded-full transition-colors ${
                          user.is_admin
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/30'
                            : 'bg-gray-700 text-gray-400 hover:bg-emerald-500/20 hover:text-emerald-400'
                        }`}
                      >
                        <UserCheck className="w-3 h-3" />
                        {user.is_admin ? 'Admin' : 'User'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
