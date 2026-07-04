import { Outlet, createRootRoute } from '@tanstack/react-router'

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <Outlet />
    </div>
  ),
})
