import { apiClient } from './client';
import type { Approval } from '../types';

export async function registerDevice(fcmToken: string): Promise<void> {
  await apiClient.post('/api/v1/devices', { fcm_token: fcmToken, platform: 'android' });
}

export async function getApprovals(): Promise<Approval[]> {
  const { data } = await apiClient.get<Approval[]>('/api/v1/approvals');
  return data;
}

export async function grantApproval(approvalId: string): Promise<void> {
  await apiClient.post(`/api/v1/approvals/${approvalId}/grant`);
}

export async function denyApproval(approvalId: string): Promise<void> {
  await apiClient.post(`/api/v1/approvals/${approvalId}/deny`);
}
