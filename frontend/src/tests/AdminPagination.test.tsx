import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AdminPagination, ADMIN_PAGE_SIZE } from '../components/admin/AdminPagination';

describe('AdminPagination', () => {
  it('uses ten records per page and navigates within the valid range', () => {
    const onPageChange = vi.fn();

    render(
      <AdminPagination
        page={2}
        pages={3}
        total={25}
        itemLabel="người dùng"
        onPageChange={onPageChange}
      />
    );

    expect(ADMIN_PAGE_SIZE).toBe(10);
    expect(screen.getByText('11–20')).toBeInTheDocument();
    expect(screen.getByText(/Trang 2\/3/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Trang trước' }));
    fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));

    expect(onPageChange).toHaveBeenNthCalledWith(1, 1);
    expect(onPageChange).toHaveBeenNthCalledWith(2, 3);
  });

  it('disables navigation at the first and only page', () => {
    render(
      <AdminPagination
        page={1}
        pages={1}
        total={5}
        itemLabel="người dùng"
        onPageChange={() => {}}
      />
    );

    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled();
    expect(screen.getByText('1–5')).toBeInTheDocument();
  });
});
