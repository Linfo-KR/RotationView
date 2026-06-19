import React from 'react';

const InfoOverlay = ({ route }) => {
  if (!route) return null;

  return (
    <>
      {/* Top Left: Route Info Panel (Glassmorphism & Compact) */}
      <div className="absolute top-4 left-14 z-[1000] bg-white/80 backdrop-blur-md shadow-2xl rounded-xl overflow-hidden border border-white/40 w-[calc(100%-80px)] sm:w-auto sm:max-w-md md:max-w-xl animate-fade-in transition-all">
        {/* Header */}
        <div className="bg-[#003399]/90 text-white px-4 py-3 flex justify-between items-center backdrop-blur-sm">
          <h2 className="text-sm md:text-base font-extrabold tracking-wide truncate pr-3 shadow-sm">
            {route.sort_idx && route.region ? <span className="mr-2 text-yellow-400">[{route.sort_idx}_{route.region}]</span> : ''}
            {route.route_name || route.svc || 'Service Route'}
          </h2>
          <span className="text-[10px] md:text-xs bg-white/20 border border-white/30 text-white px-2.5 py-1 rounded-md font-bold whitespace-nowrap tracking-wider shadow-inner">{route.svc}</span>
        </div>

        {/* Info Grid */}
        <div className="grid grid-cols-4 divide-x divide-gray-300/50 border-b border-gray-300/50 text-center text-[10px] md:text-xs font-bold text-[#002060] bg-gradient-to-b from-white/60 to-transparent">
          <div className="py-2 opacity-80 uppercase tracking-widest text-[9px] md:text-[10px]">Carriers</div>
          <div className="py-2 opacity-80 uppercase tracking-widest text-[9px] md:text-[10px]">Duration</div>
          <div className="py-2 opacity-80 uppercase tracking-widest text-[9px] md:text-[10px]">Freq</div>
          <div className="py-2 opacity-80 uppercase tracking-widest text-[9px] md:text-[10px]">Ships</div>
        </div>
        <div className="grid grid-cols-4 divide-x divide-gray-300/50 text-center text-[11px] md:text-sm text-gray-800 font-semibold bg-white/30 mb-1">
          <div className="py-2 px-1 truncate" title={route.carriers ? route.carriers.replace('OMA', 'CMA') : ''}>
            {route.carriers ? route.carriers.replace('OMA', 'CMA') : '-'}
          </div>
          <div className="py-2 px-1">{route.duration ? `${route.duration}d` : '-'}</div>
          <div className="py-2 px-1 truncate" title={route.frequency}>{route.frequency || '-'}</div>
          <div className="py-2 px-1 truncate" title={route.ships}>{route.ships || '-'}</div>
        </div>

        {/* Rotation */}
        <div className="px-4 pt-1 pb-1 text-[10px] font-bold text-[#002060]/70 uppercase tracking-widest">
          Rotation Details
        </div>
        <div className="px-4 pb-4 pt-1 text-sm md:text-[15px] text-gray-800 leading-relaxed max-h-32 md:max-h-40 overflow-y-auto custom-scrollbar">
          {(() => {
            const ports = route.port_rotation ? route.port_rotation.split(/[,\->]+/).map(p => p.trim()).filter(Boolean) : [];
            return ports.map((p, i) => {
              let styleClass = "font-medium";
              const lowerP = p.toLowerCase();
              if (lowerP.includes("busan")) {
                styleClass = "text-[#00994d] font-extrabold text-[16px] md:text-[17px] underline decoration-2 underline-offset-4";
              } else if (i === 0 || i === ports.length - 1) {
                styleClass = "text-[#d97706] font-extrabold";
              }
              return (
                <span key={i} className="inline-block whitespace-nowrap">
                  <span className={styleClass}>{p}</span>
                  {i < ports.length - 1 && <span className="text-gray-400/70 font-light mx-1.5 md:mx-2 align-middle">➔</span>}
                </span>
              );
            });
          })()}
        </div>
      </div>

      {/* Top Right: Schedule Panel */}
      {route.proforma && route.proforma.length > 0 && (
        <div className="hidden sm:flex flex-col absolute top-4 right-4 z-[1000] bg-white/95 backdrop-blur-xl shadow-2xl rounded-xl border border-gray-200/60 w-48 md:w-56 lg:w-64 max-h-[75vh] animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="bg-[#002060] text-white px-3 py-2.5 text-center shadow-md z-10 flex items-center justify-between">
            <div className="font-extrabold text-sm tracking-wide">Busan Schedule</div>
            <span className="bg-blue-500/30 font-mono px-2 py-0.5 rounded text-xs font-bold border border-blue-400/30">
              {route.proforma.length}
            </span>
          </div>
          
          {/* Schedule List */}
          <div className="p-2 md:p-3 overflow-y-auto custom-scrollbar flex-1 bg-gray-50/50 space-y-2.5">
            {route.proforma.map((pf, idx) => (
              <div key={idx} className="bg-white border text-left border-gray-100 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow">
                 <div className="flex justify-between items-center mb-1.5">
                   <h3 className="font-bold text-[#002060] text-[13px] md:text-sm tracking-tight truncate">
                     {pf.terminal_name}
                   </h3>
                   <span className="text-[10px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-bold shadow-sm">
                     #{pf.seq}
                   </span>
                 </div>
                 
                 <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                   <div className="bg-gray-50 rounded px-2 py-1.5 flex flex-col justify-center">
                     <span className="text-[9px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">W-T/P</span>
                     <span className="text-xs font-bold text-gray-700 truncate">{pf.wtp || '-'}</span>
                   </div>
                   <div className="bg-blue-50/50 rounded px-2 py-1.5 flex flex-col justify-center border border-blue-100/30">
                     <span className="text-[9px] text-blue-400 font-bold uppercase tracking-wider mb-0.5">Schedule</span>
                     <span className="text-[11px] font-bold text-blue-800 leading-tight">{pf.sch || '-'}</span>
                   </div>
                 </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
};

export default InfoOverlay;