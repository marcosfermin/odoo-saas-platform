import React, { useEffect, useState } from 'react';
import { subscriptionsApi } from '../services/api';

interface Subscription {
  id: string;
  customer_id: string;
  plan_id: string;
  status: string;
  billing_cycle: string;
  current_period_start: string;
  current_period_end: string;
  payment_provider: string;
  external_subscription_id: string;
  created_at: string;
  customer?: {
    id: string;
    email: string;
    company: string;
  };
  plan?: {
    id: string;
    name: string;
    price_monthly: number;
  };
}

interface Pagination {
  page: number;
  pages: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

export default function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchSubscriptions();
  }, [page, statusFilter]);

  const fetchSubscriptions = async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, per_page: 20 };
      if (statusFilter) params.status = statusFilter;

      const response = await subscriptionsApi.list(params);
      setSubscriptions(response.data.subscriptions);
      setPagination(response.data.pagination);
    } catch (error) {
      console.error('Failed to fetch subscriptions:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'trialing': return 'bg-blue-100 text-blue-800';
      case 'past_due': return 'bg-yellow-100 text-yellow-800';
      case 'canceled': return 'bg-red-100 text-red-800';
      case 'unpaid': return 'bg-orange-100 text-orange-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div>
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Subscriptions</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage customer subscriptions and billing status.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="trialing">Trialing</option>
          <option value="past_due">Past Due</option>
          <option value="canceled">Canceled</option>
          <option value="unpaid">Unpaid</option>
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
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Customer</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Plan</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Status</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Billing</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Provider</th>
                      <th className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">Period End</th>
                      <th className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {subscriptions.map((sub) => (
                      <tr key={sub.id}>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <div className="text-gray-900">{sub.customer?.email || '-'}</div>
                          <div className="text-xs text-gray-500">{sub.customer?.company}</div>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                          {sub.plan?.name || '-'}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm">
                          <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${getStatusBadgeColor(sub.status)}`}>
                            {sub.status}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {sub.billing_cycle}
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          <span className="capitalize">{sub.payment_provider || '-'}</span>
                        </td>
                        <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                          {sub.current_period_end
                            ? new Date(sub.current_period_end).toLocaleDateString()
                            : '-'}
                        </td>
                        <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                          <button className="text-blue-600 hover:text-blue-900">
                            View
                          </button>
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
