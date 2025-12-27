import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {}, {
            headers: { Authorization: `Bearer ${refreshToken}` }
          });

          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    }

    return Promise.reject(error);
  }
);

export default api;

// API service functions
export const dashboardApi = {
  getStats: () => api.get('/dashboard/stats'),
  getChartData: (type: string, days: number = 30) => api.get(`/dashboard/charts/${type}?days=${days}`),
  getRecentActivity: (limit: number = 20) => api.get(`/dashboard/recent-activity?limit=${limit}`),
  getAlerts: () => api.get('/dashboard/alerts'),
  getHealthSummary: () => api.get('/dashboard/health-summary'),
};

export const tenantsApi = {
  list: (params?: Record<string, any>) => api.get('/tenants/', { params }),
  get: (id: string) => api.get(`/tenants/${id}`),
  create: (data: any) => api.post('/tenants/', data),
  update: (id: string, data: any) => api.put(`/tenants/${id}`, data),
  delete: (id: string) => api.delete(`/tenants/${id}`),
  suspend: (id: string) => api.post(`/tenants/${id}/suspend`),
  unsuspend: (id: string) => api.post(`/tenants/${id}/unsuspend`),
  backup: (id: string) => api.post(`/tenants/${id}/backup`),
};

export const customersApi = {
  list: (params?: Record<string, any>) => api.get('/customers/', { params }),
  get: (id: string) => api.get(`/customers/${id}`),
  create: (data: any) => api.post('/customers/', data),
  update: (id: string, data: any) => api.put(`/customers/${id}`, data),
  delete: (id: string) => api.delete(`/customers/${id}`),
  resetPassword: (id: string, newPassword: string) => api.post(`/customers/${id}/reset-password`, { new_password: newPassword }),
};

export const plansApi = {
  list: (params?: Record<string, any>) => api.get('/plans/', { params }),
  get: (id: string) => api.get(`/plans/${id}`),
  create: (data: any) => api.post('/plans/', data),
  update: (id: string, data: any) => api.put(`/plans/${id}`, data),
  delete: (id: string) => api.delete(`/plans/${id}`),
  activate: (id: string) => api.post(`/plans/${id}/activate`),
  deactivate: (id: string) => api.post(`/plans/${id}/deactivate`),
};

export const auditApi = {
  list: (params?: Record<string, any>) => api.get('/audit/', { params }),
  get: (id: string) => api.get(`/audit/${id}`),
  getStats: () => api.get('/audit/stats'),
  getActions: () => api.get('/audit/actions'),
  export: (params: Record<string, any>) => api.get('/audit/export', { params }),
};

export const subscriptionsApi = {
  list: (params?: Record<string, any>) => api.get('/subscriptions/', { params }),
  get: (id: string) => api.get(`/subscriptions/${id}`),
  cancel: (id: string) => api.post(`/subscriptions/${id}/cancel`),
};

export const authApi = {
  login: (email: string, password: string) => api.post('/auth/login', { email, password }),
  logout: () => api.post('/auth/logout'),
  refresh: () => api.post('/auth/refresh'),
  me: () => api.get('/auth/me'),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
};
