import React, { useEffect, useState } from 'react';
import { dashboardApi } from '../services/api';
import {
  UsersIcon,
  ServerStackIcon,
  CreditCardIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

interface Stats {
  customers: {
    total: number;
    active: number;
    new_24h: number;
  };
  tenants: {
    total: number;
    active: number;
    suspended: number;
    error: number;
  };
  subscriptions: {
    total: number;
    active: number;
    trialing: number;
  };
  revenue: {
    last_30d: number;
  };
}

interface Alert {
  type: string;
  title: string;
  message: string;
  action_url: string;
}

interface Activity {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  actor_email: string;
  created_at: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, alertsRes, activityRes] = await Promise.all([
        dashboardApi.getStats(),
        dashboardApi.getAlerts(),
        dashboardApi.getRecentActivity(10),
      ]);

      setStats(statsRes.data.statistics);
      setAlerts(alertsRes.data.alerts);
      setActivities(activityRes.data.activities);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const statCards = [
    {
      name: 'Total Customers',
      value: stats?.customers.total || 0,
      icon: UsersIcon,
      change: `+${stats?.customers.new_24h || 0} today`,
      color: 'bg-blue-500',
    },
    {
      name: 'Active Tenants',
      value: stats?.tenants.active || 0,
      icon: ServerStackIcon,
      change: `${stats?.tenants.total || 0} total`,
      color: 'bg-green-500',
    },
    {
      name: 'Active Subscriptions',
      value: stats?.subscriptions.active || 0,
      icon: CreditCardIcon,
      change: `${stats?.subscriptions.trialing || 0} trialing`,
      color: 'bg-purple-500',
    },
    {
      name: 'Revenue (30d)',
      value: `$${(stats?.revenue.last_30d || 0).toLocaleString()}`,
      icon: CreditCardIcon,
      change: 'USD',
      color: 'bg-yellow-500',
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>

      {/* Stats Grid */}
      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <div key={stat.name} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className={`flex-shrink-0 ${stat.color} rounded-md p-3`}>
                  <stat.icon className="h-6 w-6 text-white" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">{stat.name}</dt>
                    <dd className="flex items-baseline">
                      <div className="text-2xl font-semibold text-gray-900">{stat.value}</div>
                      <span className="ml-2 text-sm text-gray-500">{stat.change}</span>
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-medium text-gray-900">System Alerts</h2>
          <div className="mt-4 space-y-4">
            {alerts.map((alert, index) => (
              <div
                key={index}
                className={`rounded-md p-4 ${
                  alert.type === 'error'
                    ? 'bg-red-50 border border-red-200'
                    : alert.type === 'warning'
                    ? 'bg-yellow-50 border border-yellow-200'
                    : 'bg-blue-50 border border-blue-200'
                }`}
              >
                <div className="flex">
                  <div className="flex-shrink-0">
                    <ExclamationTriangleIcon
                      className={`h-5 w-5 ${
                        alert.type === 'error'
                          ? 'text-red-400'
                          : alert.type === 'warning'
                          ? 'text-yellow-400'
                          : 'text-blue-400'
                      }`}
                    />
                  </div>
                  <div className="ml-3">
                    <h3
                      className={`text-sm font-medium ${
                        alert.type === 'error'
                          ? 'text-red-800'
                          : alert.type === 'warning'
                          ? 'text-yellow-800'
                          : 'text-blue-800'
                      }`}
                    >
                      {alert.title}
                    </h3>
                    <p
                      className={`mt-1 text-sm ${
                        alert.type === 'error'
                          ? 'text-red-700'
                          : alert.type === 'warning'
                          ? 'text-yellow-700'
                          : 'text-blue-700'
                      }`}
                    >
                      {alert.message}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity */}
      <div className="mt-8">
        <h2 className="text-lg font-medium text-gray-900">Recent Activity</h2>
        <div className="mt-4 bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {activities.map((activity) => (
              <li key={activity.id}>
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-blue-600 truncate">
                      {activity.action} - {activity.resource_type}
                    </p>
                    <div className="ml-2 flex-shrink-0 flex">
                      <p className="text-sm text-gray-500">
                        {new Date(activity.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <div className="mt-2 sm:flex sm:justify-between">
                    <div className="sm:flex">
                      <p className="text-sm text-gray-500">
                        by {activity.actor_email || 'System'}
                      </p>
                    </div>
                    <div className="mt-2 sm:mt-0">
                      <p className="text-xs text-gray-400">ID: {activity.resource_id}</p>
                    </div>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
