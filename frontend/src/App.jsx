import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './features/auth/ProtectedRoute'
import AppLayout from './components/AppLayout'
import Login from './features/auth/Login'
import Dashboard from './features/dashboard/Dashboard'
import Patients from './features/patients/Patients'
import Analysis from './features/analysis/Analysis'
import Appointments from './features/appointments/Appointments'
import Review from './features/analysis/Review'


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="patients" element={<Patients />} />
          <Route path="analysis" element={<Analysis />} />
          <Route path="analysis/:id" element={<Review />} />
          <Route path="appointments" element={<Appointments />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}