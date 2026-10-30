import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './features/auth/ProtectedRoute'
import AppLayout from './components/AppLayout'
import Login from './features/auth/Login'
import Dashboard from './features/dashboard/Dashboard'
import Patients from './features/patients/Patients'
import Analysis from './features/analysis/Analysis'
import Appointments from './features/appointments/Appointments'
import Review from './features/analysis/Review'
import PatientFile from './features/patients/PatientFile'
import Reports from './features/reports/Reports'
import ReportEditor from './features/reports/ReportEditor'
import Notifications from './features/notifications/Notifications'
import Settings from './features/settings/Settings'




export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="patients" element={<Patients />} />
          <Route path="patients/:id" element={<PatientFile />} />
          <Route path="analysis" element={<Analysis />} />
          <Route path="analysis/:id" element={<Review />} />
          <Route path="appointments" element={<Appointments />} />
          <Route path="reports" element={<Reports />} />
          <Route path="reports/:id" element={<ReportEditor />} />  
          <Route path="notifications" element={<Notifications />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}