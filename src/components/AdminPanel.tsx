import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, getUsers, updateUser, deleteUser, getPlatformStats, PlatformStats } from '../services/api';

export default function AdminPanel() {
  const { user, logout } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<User>>({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usersData, statsData] = await Promise.all([
        getUsers(),
        getPlatformStats()
      ]);
      setUsers(usersData);
      setStats(statsData);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user.id);
    setEditForm({
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      subscription_tier: user.subscription_tier
    });
  };

  const handleSave = async (userId: string) => {
    try {
      await updateUser(userId, editForm);
      await loadData();
      setEditingUser(null);
      setEditForm({});
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleDelete = async (userId: string) => {
    if (!window.confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
      return;
    }
    try {
      await deleteUser(userId);
      await loadData();
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  const handleCancel = () => {
    setEditingUser(null);
    setEditForm({});
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-purple-100 text-purple-800 border-purple-300';
      case 'paid': return 'bg-green-100 text-green-800 border-green-300';
      case 'freemium': return 'bg-gray-100 text-gray-800 border-gray-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-lg text-gray-600">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
              <p className="text-sm text-gray-600 mt-1">User Management</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">Logged in as: <strong>{user?.email}</strong></span>
              <button
                onClick={() => window.location.href = '/'}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Back to App
              </button>
              <button
                onClick={logout}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm font-medium text-gray-600">Total Users</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">{stats.total_users}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm font-medium text-gray-600">Freemium</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">{stats.freemium_users}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm font-medium text-gray-600">Paid</div>
              <div className="text-2xl font-bold text-green-600 mt-1">{stats.paid_users}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <div className="text-sm font-medium text-gray-600">Admins</div>
              <div className="text-2xl font-bold text-purple-600 mt-1">{stats.admin_users}</div>
            </div>
          </div>
        )}

        {/* Users Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Users</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {editingUser === u.id ? (
                        <input
                          type="email"
                          value={editForm.email || ''}
                          onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                        />
                      ) : (
                        <div className="text-sm text-gray-900">{u.email}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {editingUser === u.id ? (
                        <div className="space-y-1">
                          <input
                            type="text"
                            value={editForm.first_name || ''}
                            onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                            placeholder="First name"
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                          />
                          <input
                            type="text"
                            value={editForm.last_name || ''}
                            onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                            placeholder="Last name"
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                          />
                        </div>
                      ) : (
                        <div className="text-sm text-gray-900">
                          {u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : '-'}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {editingUser === u.id ? (
                        <select
                          value={editForm.role || 'freemium'}
                          onChange={(e) => setEditForm({ ...editForm, role: e.target.value as any })}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="freemium">Freemium</option>
                          <option value="paid">Paid</option>
                          <option value="admin">Admin</option>
                        </select>
                      ) : (
                        <span className={`px-2 py-1 text-xs font-semibold rounded border ${getRoleColor(u.role)}`}>
                          {u.role}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {editingUser === u.id ? (
                        <input
                          type="text"
                          value={editForm.subscription_tier || ''}
                          onChange={(e) => setEditForm({ ...editForm, subscription_tier: e.target.value })}
                          placeholder="Subscription tier"
                          className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                        />
                      ) : (
                        <div className="text-sm text-gray-900">{u.subscription_tier || '-'}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      {editingUser === u.id ? (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSave(u.id)}
                            className="text-indigo-600 hover:text-indigo-900"
                          >
                            Save
                          </button>
                          <button
                            onClick={handleCancel}
                            className="text-gray-600 hover:text-gray-900"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleEdit(u)}
                            className="text-indigo-600 hover:text-indigo-900"
                          >
                            Edit
                          </button>
                          {u.id !== user?.id && (
                            <button
                              onClick={() => handleDelete(u.id)}
                              className="text-red-600 hover:text-red-900"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

