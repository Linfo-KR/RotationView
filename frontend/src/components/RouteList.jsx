import { useState, useEffect, useMemo } from 'react';
import { routeService } from '../services/api';

const REGIONS = [
  { id: 'ALL', name: '전체 해역' },
  { id: 'K/C/J', name: 'K/C/J' },
  { id: 'China', name: 'China' },
  { id: 'Japan', name: 'Japan' },
  { id: 'Russia', name: 'Russia' },
  { id: 'SE Asia', name: 'SE Asia' },
  { id: 'ISC', name: 'ISC' },
  { id: 'ME', name: 'ME' },
  { id: 'FE-MED', name: '지중해' },
  { id: 'FE-N.Eur', name: '북유럽' },
  { id: 'FE-ECNA', name: '미주 동안' },
  { id: 'FE-WCNA', name: '미주 서안' },
  { id: 'FE-ECSA', name: '남미 동안' },
  { id: 'FE-WCSA', name: '남미 서안' },
  { id: 'ANZ', name: '오세아니아' },
  { id: 'SAF/WAF', name: '아프리카' },
];

const RouteList = ({ onSelectRoute, selectedRouteId, isCollapsed, toggleSidebar }) => {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRegion, setSelectedRegion] = useState('ALL');
  const [page, setPage] = useState(1);
  const [years, setYears] = useState([]);
  const [selectedYear, setSelectedYear] = useState(null);
  const itemsPerPage = 20;

  // 1. Fetch available years on mount
  useEffect(() => {
    const fetchYears = async () => {
      try {
        const data = await routeService.getRouteYears();
        setYears(data);
        if (data && data.length > 0) {
          setSelectedYear(data[0]); // Default to latest year
        } else {
          setSelectedYear(2026);
        }
      } catch (err) {
        console.error("Failed to load route years", err);
        setSelectedYear(2026);
      }
    };
    fetchYears();
  }, []);

  // 2. Fetch routes when selectedYear changes
  useEffect(() => {
    if (!selectedYear) return;

    const fetchRoutes = async () => {
      setLoading(true);
      try {
        const data = await routeService.getAllRoutes(selectedYear);
        setRoutes(data);
        setPage(1); // Reset page on year change
      } catch (err) {
        console.error("Failed to load routes", err);
      } finally {
        setLoading(false);
      }
    };
    fetchRoutes();
  }, [selectedYear]);

  const filteredRoutes = useMemo(() => {
    const term = searchTerm.toLowerCase();
    return routes.filter(route => {
      const matchesSearch = 
        (route.svc && route.svc.toLowerCase().includes(term)) ||
        (route.route_name && route.route_name.toLowerCase().includes(term)) ||
        (route.carriers && route.carriers.toLowerCase().includes(term));
      
      const matchesRegion = selectedRegion === 'ALL' || route.region === selectedRegion;
      return matchesSearch && matchesRegion;
    });
  }, [routes, searchTerm, selectedRegion]);

  const paginatedRoutes = useMemo(() => {
    const start = (page - 1) * itemsPerPage;
    return filteredRoutes.slice(start, start + itemsPerPage);
  }, [filteredRoutes, page]);

  const totalPages = Math.ceil(filteredRoutes.length / itemsPerPage);

  if (isCollapsed) {
    return (
      <div className="h-full bg-white border-r border-gray-200 w-12 flex flex-col items-center py-4 cursor-pointer hover:bg-gray-50 transition-colors" onClick={toggleSidebar}>
        <span className="transform rotate-90 text-gray-500 font-bold whitespace-nowrap mt-8 tracking-widest text-xs">ROUTES</span>
        <button className="mt-4 p-2 rounded-full hover:bg-gray-200 text-gray-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" /></svg>
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white h-full flex flex-col shadow-lg relative w-full border-r border-gray-200">
      {/* Header */}
      <div className="p-4 bg-[#003399] text-white shadow-md z-10">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-bold">Service Routes</h2>
          <button onClick={toggleSidebar} className="text-white opacity-80 hover:opacity-100 p-1 rounded hover:bg-blue-800 transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" /></svg>
          </button>
        </div>

        {/* Year Toggle Switch (Segmented Control) */}
        {years.length > 0 && (
          <div className="flex bg-blue-950/60 p-1 rounded-lg mb-3 border border-blue-800/40 relative">
            {years.map(y => (
              <button
                key={y}
                type="button"
                onClick={() => setSelectedYear(y)}
                className={`flex-1 text-center py-1.5 rounded-md text-xs font-bold transition-all duration-300 z-10 ${
                  selectedYear === y
                    ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-md shadow-blue-900/30'
                    : 'text-blue-200 hover:text-white hover:bg-blue-800/30'
                }`}
              >
                {y}년 노선도
              </button>
            ))}
          </div>
        )}

        <div className="relative">
            <input 
              type="text" 
              placeholder="Search..." 
              className="w-full p-2 pl-8 rounded text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
            />
            <svg className="w-4 h-4 text-gray-400 absolute left-2 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
        </div>
      </div>

      {/* Region Filter Chips */}
      <div className="flex gap-1.5 overflow-x-auto py-2.5 px-3 bg-gray-100/80 border-b border-gray-200 scrollbar-thin">
        {REGIONS.map(r => (
          <button
            key={r.id}
            type="button"
            onClick={() => { setSelectedRegion(r.id); setPage(1); }}
            className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap border transition-all duration-200 ${
              selectedRegion === r.id
                ? 'bg-[#003399] text-white border-[#003399] shadow-sm'
                : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
            }`}
          >
            {r.name}
          </button>
        ))}
      </div>

      {/* List Content */}
      <div className="flex-1 overflow-y-auto bg-gray-50 p-2 space-y-2">
        {loading ? (
          <div className="text-center p-8 text-gray-500">Loading routes...</div>
        ) : filteredRoutes.length === 0 ? (
          <div className="text-center p-8 text-gray-500">No routes found</div>
        ) : (
          paginatedRoutes.map((route, idx) => (
            <div 
              key={route.route_idx || route.id || `route-${idx}`} // Unique Key Fix
              onClick={() => onSelectRoute(route)}
              className={`bg-white p-3 rounded-lg shadow-sm cursor-pointer border-l-[6px] hover:shadow-md transition-all duration-200 group ${
                selectedRouteId === (route.route_idx || route.id) 
                  ? 'border-[#003399] ring-1 ring-blue-100 bg-blue-50' 
                  : 'border-gray-300 hover:border-[#002060]'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-base text-[#002060] group-hover:text-[#003399]">
                    {route.svc || route.service_code || 'Unknown'}
                </span>
                {route.direction && (
                    <span className="text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded font-medium uppercase">
                    {route.direction}
                    </span>
                )}
              </div>
              
              <div className="text-xs text-gray-600 mb-2 font-medium truncate" title={route.route_name}>
                {route.route_name || '-'}
              </div>
              
              {/* Consorthium / Carrier */}
              <div className="flex items-center text-xs text-gray-500 mb-2">
                <svg className="w-3 h-3 mr-1 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>
                <span className="truncate">{route.carriers || route.consortium || 'N/A'}</span>
              </div>

              {/* Rotation Preview */}
              <div className="text-[10px] text-gray-400 border-t border-gray-100 pt-2 mt-1 truncate">
                {route.port_rotation}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination Footer */}
      <div className="p-3 bg-white border-t border-gray-200 flex justify-between items-center text-xs text-gray-600">
        <button 
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1.5 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
        >
            Prev
        </button>
        <span>
            <span className="font-bold text-[#003399]">{page}</span> / {totalPages}
        </span>
        <button 
            disabled={page === totalPages}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1.5 bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
        >
            Next
        </button>
      </div>
    </div>
  );
};

export default RouteList;