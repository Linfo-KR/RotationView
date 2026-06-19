import { useState, useEffect } from 'react';
import RouteList from './components/RouteList';
import MapVisualizer from './components/MapVisualizer';
import InfoOverlay from './components/InfoOverlay';
import RotationTimeline from './components/RotationTimeline';
import { portService, routeService } from './services/api';

import './App.css';

function App() {
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [routeDetail, setRouteDetail] = useState(null); // Full detail with Proforma
  const [allPorts, setAllPorts] = useState([]);
  const [loadingPorts, setLoadingPorts] = useState(true);
  const [portsError, setPortsError] = useState(null);
  
  // UI State
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);

  useEffect(() => {
    const fetchPorts = async () => {
      try {
        const data = await portService.getAllPorts();
        setAllPorts(data);
      } catch (error) {
        console.error("Failed to fetch ports:", error);
        setPortsError('Failed to load port data');
      } finally {
        setLoadingPorts(false);
      }
    };
    fetchPorts();
  }, []);

  const handleSelectRoute = async (route) => {
    setSelectedRoute(route); // Immediate feedback with basic data
    setRouteDetail(null); // Clear previous detail
    setIsTimelineOpen(true); // 노선 선택 시 우측 슬라이드 타임라인 자동 활성화!
    
    try {
        const id = route.route_idx || route.id;
        const detail = await routeService.getRouteById(id);
        setRouteDetail(detail);
    } catch (e) {
        console.error("Failed to load route detail", e);
        setRouteDetail(route);
    }
  };

  if (loadingPorts) {
    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-100 flex-col">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-gray-600 font-medium">Loading Global Port Database...</p>
        </div>
    );
  }

  if (portsError) {
    return <div className="flex items-center justify-center min-h-screen text-xl text-red-600">{portsError}</div>;
  }

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Sidebar Area */}
      <div 
        className={`transition-all duration-300 ease-in-out border-r border-gray-300 bg-white z-25 flex-shrink-0 ${
            isSidebarCollapsed ? 'w-16' : 'w-80'
        }`}
      >
        <RouteList 
            onSelectRoute={handleSelectRoute} 
            selectedRouteId={selectedRoute?.route_idx || selectedRoute?.id} 
            isCollapsed={isSidebarCollapsed}
            toggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />
      </div>

      {/* Main Map & Interactive Panel Area */}
      <div className="flex-1 relative overflow-hidden flex">
        <div className="flex-1 h-full relative">
          <MapVisualizer 
              selectedRoute={routeDetail || selectedRoute} 
              allPorts={allPorts} 
              isTimelineOpen={isTimelineOpen}
              onRouteUpdated={() => {
                  if (selectedRoute) {
                      handleSelectRoute(selectedRoute);
                  }
              }}
          />
          
          {/* Info Overlay (Floating on top of map) */}
          {routeDetail && (
              <InfoOverlay route={routeDetail} />
          )}

          {/* 우측 정보 패널 열렸을 때 지도 우하단 컨트롤 가림 보정을 위한 여백 토글 버튼 */}
          {selectedRoute && !isTimelineOpen && (
            <button
              onClick={() => setIsTimelineOpen(true)}
              className="absolute top-[80px] right-4 z-[1000] p-2.5 rounded-lg bg-slate-900/90 text-cyan-400 border border-slate-700/50 hover:bg-slate-800/90 shadow-xl transition-all duration-300 backdrop-blur-sm"
              title="Open Rotation Timeline"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
              </svg>
            </button>
          )}
        </div>

        {/* 🏢 우측 슬라이드 로테이션 타임라인 & 부산항 터미널 연동 패널 */}
        <RotationTimeline
          selectedRoute={routeDetail || selectedRoute}
          isOpen={isTimelineOpen}
          onClose={() => setIsTimelineOpen(false)}
          onToggle={() => setIsTimelineOpen(!isTimelineOpen)}
        />
      </div>
    </div>
  );
}

export default App;
