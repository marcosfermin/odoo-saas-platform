import React, { useEffect, useState } from 'react';
import { auditApi } from '../services/api';

interface AuditLog {
  id: string;
  actor_email: string;
  actor_role: string;
  action: string;
  resource_type: string;
  resource_id: string;
  ip_address: string;
  created_at: string;
}

interface Pagination {
  page: number;
  pages: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [resourceTypeFilter, setResourceTypeFilter] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchLogs();
  }, [page, actionFilter, resourceTypeFilter]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, per_page: 50 };
      if (actionFilter) params.action = actionFilter;
      if (resourceTypeFilter) params.resource_type = resourceTypeFilter;

      const response = await auditApi.list(params);
      setLogs(response.data.audit_logs);
      setPagination(response.data.pagination);
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const getActionBadgeColor = (action: string) => {
    switch (action) {
      case 'create': return 'bg-green-100 text-green-800';
      case 'update': return 'bg-blue-100 text-blue-800';
      case 'delete': return 'bg-red-100 text-red-800';
      case 'login': return 'bg-purple-100 text-purple-800';
      case 'logout': return 'bg-gray-100 text-gray-800';
      case 'suspend': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div>
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Audit Logs</h1>
          <p className="mt-2 text-sm text-gray-700">
            View all platform activity and changes for compliance and security monitoring.
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            Export
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 flex flex-col sm:flex-row gap-4">
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
        >
          <option value="">All Actions</option>
          <option value="create">Create</option>
          <option value="update">Update</option>
          <option value="delete">Delete</option>
          <option value="login">Login</option>
          <option value="logout">Logout</option>
          <option value="suspend">Suspend</option>
          <option value="unsuspend">Unsuspend</option>
        </select>
        <select
          value={resourceTypeFilter}
          onChange={(e) => { setResourceTypeFilter(e.target.value); setPage(1); }}
          className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
        >
          <option value="">All Resources</option>
          <option value="tenant">Tenant</option>
          <option value="customer">Customer</option>
          <option value="plan">Plan</option>
          <option value="subscription">Subscription</option>
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
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Timestamp</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Actor</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Action</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Resource</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">IP Address</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {logs.map((log) => (
                      <tr key={log.id} className="hover:bg-gray-50">
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <div className="text-gray-900">{log.actor_email || 'System'}</div>
                          <div className="text-xs text-gray-500">{log.actor_role}</div>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${getActionBadgeColor(log.action)}`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <div className="text-gray-900">{log.resource_type}</div>
                          <div className="text-xs text-gray-500 font-mono">{log.resource_id?.slice(0, 8)}...</div>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500 font-mono">
                          {log.ip_address || '-'}
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
