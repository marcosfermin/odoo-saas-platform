import React, { useEffect, useState } from 'react';
import { plansApi } from '../services/api';

interface Plan {
  id: string;
  name: string;
  description: string;
  price_monthly: number | null;
  price_yearly: number | null;
  currency: string;
  max_tenants: number;
  max_users_per_tenant: number;
  max_db_size_gb: number;
  max_filestore_gb: number;
  is_active: boolean;
  trial_days: number;
  tenant_count?: number;
  subscription_count?: number;
}

export default function Plans() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    setLoading(true);
    try {
      const response = await plansApi.list();
      setPlans(response.data.plans);
    } catch (error) {
      console.error('Failed to fetch plans:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (plan: Plan) => {
    try {
      if (plan.is_active) {
        await plansApi.deactivate(plan.id);
      } else {
        await plansApi.activate(plan.id);
      }
      fetchPlans();
    } catch (error) {
      console.error('Failed to toggle plan status:', error);
    }
  };

  return (
    <div>
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Billing Plans</h1>
          <p className="mt-2 text-sm text-gray-700">
            Configure pricing plans and their quotas.
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700"
          >
            Add Plan
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`relative bg-white rounded-lg shadow-md overflow-hidden ${
                !plan.is_active ? 'opacity-60' : ''
              }`}
            >
              {!plan.is_active && (
                <div className="absolute top-2 right-2">
                  <span className="inline-flex rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-800">
                    Inactive
                  </span>
                </div>
              )}

              <div className="p-6">
                <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                <p className="mt-2 text-sm text-gray-500">{plan.description}</p>

                <div className="mt-4">
                  <span className="text-3xl font-bold text-gray-900">
                    ${plan.price_monthly || 0}
                  </span>
                  <span className="text-gray-500">/month</span>
                </div>

                {plan.price_yearly && (
                  <p className="mt-1 text-sm text-gray-500">
                    or ${plan.price_yearly}/year
                  </p>
                )}

                <div className="mt-6 space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Max Tenants</span>
                    <span className="font-medium text-gray-900">{plan.max_tenants}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Users per Tenant</span>
                    <span className="font-medium text-gray-900">{plan.max_users_per_tenant}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Database Size</span>
                    <span className="font-medium text-gray-900">{plan.max_db_size_gb} GB</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">File Storage</span>
                    <span className="font-medium text-gray-900">{plan.max_filestore_gb} GB</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Trial Days</span>
                    <span className="font-medium text-gray-900">{plan.trial_days}</span>
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-gray-200">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Active Tenants</span>
                    <span className="font-medium text-gray-900">{plan.tenant_count || 0}</span>
                  </div>
                  <div className="flex justify-between text-sm mt-2">
                    <span className="text-gray-500">Subscriptions</span>
                    <span className="font-medium text-gray-900">{plan.subscription_count || 0}</span>
                  </div>
                </div>

                <div className="mt-6 flex gap-2">
                  <button
                    onClick={() => handleToggleActive(plan)}
                    className={`flex-1 px-3 py-2 text-sm font-medium rounded-md ${
                      plan.is_active
                        ? 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200'
                        : 'bg-green-100 text-green-800 hover:bg-green-200'
                    }`}
                  >
                    {plan.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200">
                    Edit
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
