import { apiClient } from './client';
import type { Approval } from '../types';

export async function registerDevice(fcmToken: string): Promise<void> {
  await apiClient.post('/api/v1/devices', { fcm_token: fcmToken, platform: 'android' });
}

export async function getApprovals(): Promise<Approval[]> {
  const { data } = await apiClient.get<{
    approvals: Array<{
      id: string;
      taskId?: string;
      task_id: string;
      description: string;
      requestedAt?: string;
      created_at: string;
    }>;
  }>('/api/v1/approvals');
  return data.approvals.map((approval) => ({
    id: approval.id,
    taskId: approval.taskId ?? approval.task_id,
    description: approval.description,
    requestedAt: approval.requestedAt ?? approval.created_at,
  }));
}

export async function grantApproval(approvalId: string): Promise<void> {
  await apiClient.post(`/api/v1/approvals/${approvalId}/grant`);
}

export async function denyApproval(approvalId: string): Promise<void> {
  await apiClient.post(`/api/v1/approvals/${approvalId}/deny`);
}
