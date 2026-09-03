
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Home } from './pages/Home'
import { Recover } from './pages/Recover'
import { Discover } from './pages/Discover'
import { Understand } from './pages/Understand'
import { Manage } from './pages/Manage'
import { Protect } from './pages/Protect'
import { Track } from './pages/Track'
import { RecoveryCase } from './pages/RecoveryCase'
import { Transactions } from './pages/Transactions'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/recover" element={<Recover />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/understand" element={<Understand />} />
        <Route path="/manage" element={<Manage />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/protect" element={<Protect />} />
        <Route path="/track" element={<Track />} />
        <Route path="/recovery/:id" element={<RecoveryCase />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
