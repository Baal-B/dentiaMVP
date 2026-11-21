import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './features/auth/ProtectedRoute'
import { DoctorOnly, SecretaryOnly } from './features/auth/RoleRoutes'
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
import Prescriptions from './features/prescriptions/Prescriptions'
import PrescriptionEditor from './features/prescriptions/PrescriptionEditor'
import PublicBooking from './features/booking/PublicBooking'
import SecretaryLayout from './features/secretary/SecretaryLayout'
import Requests from './features/secretary/Requests'
import SecretaryAgenda from './features/secretary/SecretaryAgenda'
import SecretaryPatients from './features/secretary/SecretaryPatients'
import Cabinets from './features/booking/Cabinets'
import Events from './features/events/Events'
import Assistant from './features/assistant/Assistant'


export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/reserver/:slug" element={<PublicBooking />} />
      <Route path="/cabinets" element={<Cabinets />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<DoctorOnly />}>
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
            <Route path="events" element={<Events />} />
            <Route path="assistant" element={<Assistant />} />
            <Route path="settings" element={<Settings />} />
            <Route path="prescriptions" element={<Prescriptions />} />
            <Route path="prescriptions/:id" element={<PrescriptionEditor />} />
            <Route path="requests" element={<Requests />} />    {/* new: the doctor sees the inbox too */}
          </Route>
        </Route>

        <Route element={<SecretaryOnly />}>
          <Route path="/secretary" element={<SecretaryLayout />}>
            <Route index element={<Requests />} />
            <Route path="agenda" element={<SecretaryAgenda />} />
            <Route path="patients" element={<SecretaryPatients />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}