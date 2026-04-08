import axios from 'axios';
import {
  getApiRuntimeState,
  handleUnauthorizedResponse,
} from './runtime';

export const apiClient = axios.create({
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const { serverUrl, jwtToken } = getApiRuntimeState();
  config.baseURL = serverUrl;
  if (jwtToken) config.headers.Authorization = `Bearer ${jwtToken}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await handleUnauthorizedResponse();
    }
    return Promise.reject(error);
  },
);
