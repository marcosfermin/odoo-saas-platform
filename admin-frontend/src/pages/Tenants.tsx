import React, { useEffect, useState } from 'react';
import { tenantsApi } from '../services/api';

interface Tenant {
  id: string;
  slug: string;
  name: string;
  state: string;
  db_name: string;
  current_users: number;
  created_at: string;
  customer?: {
    id: string;
    email: string;
    company: string;
  };
  plan?: {
    id: string;
    name: string;
  };
}

interface Pagination {
  page: number;
  pages: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

export default function Tenants() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchTenants();
  }, [page, stateFilter]);

  const fetchTenants = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, per_page: 20 };
      if (search) params.search = search;
      if (stateFilter) params.state = stateFilter;

      const response = await tenantsApi.list(params);
      setTenants(response.data.tenants);
      setPagination(response.data.pagination);
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTenants();
  };

  const handleSuspend = async (id: string) => {
    if (!window.confirm('Are you sure you want to suspend this tenant?')) return;
    try {
      await tenantsApi.suspend(id);
      fetchTenants();
    } catch (error) {
      console.error('Failed to suspend tenant:', error);
    }
  };

  const handleUnsuspend = async (id: string) => {
    try {
      await tenantsApi.unsuspend(id);
      fetchTenants();
    } catch (error) {
      console.error('Failed to unsuspend tenant:', error);
    }
  };

  const getStateBadgeColor = (state: string) => {
    switch (state) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'suspended': return 'bg-yellow-100 text-yellow-800';
      case 'creating': return 'bg-blue-100 text-blue-800';
      case 'error': return 'bg-red-100 text-red-800';
      case 'deleted': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div>
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Tenants</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage all Odoo tenant instances across the platform.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-col sm:flex-row gap-4">
        <form onSubmit={handleSearch} className="flex-1">
          <input
            type="text"
            placeholder="Search by name or slug..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          />
        </form>
        <select
          value={stateFilter}
          onChange={(e) => { setStateFilter(e.target.value); setPage(1); }}
          className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
        >
          <option value="">All States</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="creating">Creating</option>
          <option value="error">Error</option>
        </select>
      </div>

      {/* Table */}
      <div className="mt-8 flex flex-col">
        <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div className="inline-block min-w-full py-2 align-middle md:px-6 lg:px-8">
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
              {loading ? (
                <div className="flex items-center justify-center h-64 bg-white">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : (
                <table className="min-w-full divide-y divide-gray-300">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Tenant</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Customer</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Plan</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">State</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Users</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Created</th>
                      <th className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {tenants.map((tenant) => (
                      <tr key={tenant.id}>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <div className="font-medium text-gray-900">{tenant.name}</div>
                          <div className="text-gray-500">{tenant.slug}</div>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {tenant.customer?.email || '-'}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {tenant.plan?.name || '-'}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${getStateBadgeColor(tenant.state)}`}>
                            {tenant.state}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {tenant.current_users}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {new Date(tenant.created_at).toLocaleDateString()}
                        </td>
                        <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                          {tenant.state === 'active' && (
                            <button
                              onClick={() => handleSuspend(tenant.id)}
                              className="text-yellow-600 hover:text-yellow-900 mr-4"
                            >
                              Suspend
                            </button>
                          )}
                          {tenant.state === 'suspended' && (
                            <button
                              onClick={() => handleUnsuspend(tenant.id)}
                              className="text-green-600 hover:text-green-900 mr-4"
                            >
                              Unsuspend
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Pagination */}
      {pagination && pagination.pages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            Showing page {pagination.page} of {pagination.pages} ({pagination.total} total)
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(page - 1)}
              disabled={!pagination.has_prev}
              className="px-3 py-1 border rounded-md disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={!pagination.has_next}
              className="px-3 py-1 border rounded-md disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
