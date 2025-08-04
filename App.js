import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react"; 
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Languages from "./pages/Languages";
import Genres from "./pages/Genres";
import People from "./pages/People";
import Settings from "./pages/Settings";
import MovieDetails from "./pages/MovieDetails";
import PersonDetails from "./pages/PersonDetails";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import ProfileSelector from "./pages/ProfileSelector";
import ProtectedRoute from "./components/ProtectedRoute";
import InfoModal from "./components/Info";
import Chatbot from "./components/Chatbot";
import SplashScreen from "./components/SplashScreen";
import { jwtDecode } from "jwt-decode";
import { Toaster } from "react-hot-toast";
import { UserProvider } from "./context/UserContext";

function App() {

  const [showSplash, setShowSplash] = useState(true);

  const [authState, setAuthState] = useState({
    isAuthenticated: false,
    isLoading: true,
    user: null,
    selectedProfile: null,
    profiles: [],
    isAdmin: false,
    isSidebarOpen: false,
    isInfoOpen: false,
  });

  const { isSidebarOpen, isInfoOpen, user, selectedProfile, profiles, isAdmin } = authState;

  const setInfoOpen = (open) => {
    setAuthState(prevState => ({ ...prevState, isInfoOpen: open }));
  };

  const setSidebarOpen = (open) => {
    setAuthState(prevState => ({ ...prevState, isSidebarOpen: open }));
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setAuthState({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      selectedProfile: null,
      profiles: [],
      isAdmin: false,
      isSidebarOpen: false,
      isInfoOpen: false,
    });
  };

  const fetchUserProfiles = useCallback(async (token, userData) => {
    try {
      const response = await fetch("http://localhost:5000/user/profiles", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) throw new Error("Failed to fetch profiles");
      const profiles = await response.json();

      setAuthState(prev => ({
        ...prev,
        isAuthenticated: true,
        isLoading: false,
        user: userData,
        selectedProfile: null,
        profiles,
        isAdmin: false,
      }));
    } catch (error) {
      console.error("Error fetching profiles:", error);
      setAuthState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  const handleLogin = (token, userData) => {
    localStorage.setItem("token", token);

    if (userData.is_admin) {
      setAuthState(prev => ({
        ...prev,
        isAuthenticated: true,
        isLoading: false,
        user: userData,
        selectedProfile: { name: "Admin", profile_emoji: "👑", is_admin: true },
        profiles: [],
        isAdmin: true,
      }));
      return;
    }

    fetchUserProfiles(token, userData);
  };

  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem("token");
      if (!token) {
        setAuthState(prev => ({ ...prev, isLoading: false }));
        return;
      }

      try {
        const decoded = jwtDecode(token);
        const response = await fetch("http://localhost:5000/user/profile", {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) throw new Error("Invalid token");
        const userData = await response.json();

        if (userData.is_admin) {
          setAuthState(prev => ({
            ...prev,
            isAuthenticated: true,
            isLoading: false,
            user: decoded,
            selectedProfile: { name: "Admin", profile_emoji: "👑", is_admin: true },
            isAdmin: true,
          }));
        } else {
          await fetchUserProfiles(token, decoded);
        }
      } catch (error) {
        console.error("Auth error:", error);
        localStorage.removeItem("token");
        setAuthState(prev => ({ ...prev, isLoading: false }));
      }
    };

    initializeAuth();
  }, [fetchUserProfiles]);

  // --- Profile update handler for Settings.js ---
  const handleProfileUpdate = (updatedProfile) => {
    setAuthState(prev => {
      const idx = prev.profiles.findIndex(
        p => p.name === prev.selectedProfile?.name && p.profile_emoji === prev.selectedProfile?.profile_emoji
      );
      let newProfiles = [...prev.profiles];
      if (idx !== -1) {
        newProfiles[idx] = { ...newProfiles[idx], ...updatedProfile };
      }
      return {
        ...prev,
        selectedProfile: { ...prev.selectedProfile, ...updatedProfile },
        profiles: newProfiles,
      };
    });
  };

  if (showSplash) {
    return <SplashScreen onComplete={() => setShowSplash(false)} />;
  }

  if (authState.isLoading) {
    return <div className="loading-screen">Loading...</div>;
  }

  return (
    <UserProvider>
      <Toaster position="top-center" reverseOrder={false} />
      {!authState.isAuthenticated ? (
        <Routes>
          <Route path="/login" element={<Login onLogin={handleLogin} />} />
          <Route path="/register" element={<Register onLogin={handleLogin} />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      ) : authState.isAdmin || authState.selectedProfile ? (
        <div className="flex bg-gray-900 text-white min-h-screen relative">
          <Sidebar
            isOpen={isSidebarOpen}
            setIsOpen={setSidebarOpen}
            user={isAdmin ? user : selectedProfile}
            onLogout={handleLogout}
          />
          <div className="flex-1">
            <Navbar setInfoOpen={setInfoOpen} user={isAdmin ? user : selectedProfile} />
            <Routes>
              <Route path="/" element={<ProtectedRoute><Home profile={isAdmin ? user : selectedProfile} /></ProtectedRoute>} />
              <Route path="/languages" element={<ProtectedRoute><Languages /></ProtectedRoute>} />
              <Route path="/genres" element={<ProtectedRoute><Genres /></ProtectedRoute>} />
              <Route path="/people" element={<ProtectedRoute><People /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute><Settings profile={isAdmin ? user : selectedProfile} profiles={profiles} onProfileUpdate={handleProfileUpdate} /></ProtectedRoute>} />
              <Route path="/movie/:id" element={<ProtectedRoute><MovieDetails profile={isAdmin ? user : selectedProfile} /></ProtectedRoute>} />
              <Route path="/person/:id" element={<ProtectedRoute><PersonDetails /></ProtectedRoute>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
          <InfoModal isOpen={isInfoOpen} onClose={() => setInfoOpen(false)} />
          <Chatbot />
        </div>
      ) : (
        <ProfileSelector
          profiles={profiles}
          onSelectProfile={(profile) =>
            setAuthState(prev => ({ ...prev, selectedProfile: profile }))
          }
          onCreateProfile={(newProfile) =>
            setAuthState(prev => ({ ...prev, profiles: [...prev.profiles, newProfile] }))
          }
        />
      )}
    </UserProvider>
  );
}

export default App;