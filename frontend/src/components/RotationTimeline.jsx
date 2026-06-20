import { useMemo, useState } from 'react';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import { getOptimizedBounds } from './map/mapHelpers';

/**
 * RotationTimeline - 노선의 기항지 순서(Rotation) 및 부산항 상하역 터미널 스케줄(Proforma)을
 * 우측 영역에 슬라이드 인 형태로 우아하게 노출하는 프리미엄 대시보드 컴포넌트입니다.
 * 좌측 가장자리에 밀착된 일체형 플로팅 세로 탭을 통해 상시 접고 펴기가 가능합니다.
 */
const RotationTimeline = ({ selectedRoute, isOpen, onClose, onToggle }) => {
  const [exporting, setExporting] = useState(false);

  const handleExportPDF = async () => {
    if (!selectedRoute) return;
    setExporting(true);

    try {
      // 1. 최적 바운즈 획득을 위한 좌표 정보 수집
      let allPoints = [];
      if (selectedRoute.coordinates) {
        const coords = selectedRoute.coordinates;
        if (Array.isArray(coords)) {
          allPoints = coords;
        } else {
          if (coords.outbound) coords.outbound.forEach(line => allPoints.push(...line));
          if (coords.inbound) coords.inbound.forEach(line => allPoints.push(...line));
        }
      }

      const mapInstance = window.leafletMap;
      let oldCenter = null;
      let oldZoom = null;

      // 2. 지도 최적 Fit-Bounds 강제 적용 (캡처용)
      if (mapInstance && allPoints.length > 0) {
        oldCenter = mapInstance.getCenter();
        oldZoom = mapInstance.getZoom();
        const boundsData = getOptimizedBounds(allPoints);
        if (boundsData) {
          mapInstance.fitBounds(boundsData, { animate: false, padding: [40, 40] });
        }
        // 타일 및 마커의 렌더링 동기화를 위해 대기
        await new Promise((resolve) => setTimeout(resolve, 800));
      }

      // 3. 지도 및 타임라인 영역 캡처
      const mapEl = document.querySelector('.leaflet-container');
      const timelineEl = document.querySelector('#timeline-scroll-container');
      
      if (!mapEl || !timelineEl) {
        alert("지도 또는 타임라인 영역을 찾을 수 없습니다.");
        return;
      }

      const mapCanvas = await html2canvas(mapEl, {
        useCORS: true,
        logging: false,
        scale: 2 // 고해상도 캡처
      });

      // 원래 사용자의 맵 뷰로 원복
      if (mapInstance && oldCenter && oldZoom) {
        mapInstance.setView(oldCenter, oldZoom, { animate: false });
      }

      // 타임라인 캡처 (가려진 스크롤 포함 전체 영역 캡처)
      const timelineCanvas = await html2canvas(timelineEl, {
        useCORS: true,
        logging: false,
        scale: 2,
        height: timelineEl.scrollHeight, // 스크롤 전체 높이 캡처
        windowHeight: timelineEl.scrollHeight
      });

      // 4. 고해상도 PDF 직조 (A4 Landscape, 297mm x 210mm)
      const doc = new jsPDF({
        orientation: 'landscape',
        unit: 'mm',
        format: 'a4'
      });

      // 테마 배경색 및 장식선 추가 (슬레이트/네이비 프리미엄 브랜딩)
      doc.setFillColor(15, 23, 42); // slate-900 헤더 배경
      doc.rect(0, 0, 297, 35, 'F');

      // 헤더 텍스트
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(16);
      doc.setTextColor(56, 189, 248); // sky-400
      doc.text("BPA PORT ROTATION REPORT", 15, 13);

      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(203, 213, 225); // slate-300
      doc.text(`Service Route: ${selectedRoute.svc || 'N/A'} - ${selectedRoute.route_name || 'N/A'}`, 15, 21);
      doc.text(`Carriers: ${selectedRoute.carriers || 'N/A'}   |   Vessels: ${selectedRoute.ships || 'N/A'}   |   Duration: ${selectedRoute.duration ? `${selectedRoute.duration} Days` : 'N/A'}`, 15, 27);

      // 본문 콘텐츠 배치 (A4에 최적화된 비율 계산)
      // 1) 좌측 지도 이미지
      const mapImgData = mapCanvas.toDataURL('image/png');
      doc.setFillColor(248, 250, 252); // slate-50 본문 배경
      doc.rect(12, 42, 166, 154, 'F');
      doc.setDrawColor(226, 232, 240); // slate-200 테두리
      doc.rect(12, 42, 166, 154, 'S');
      doc.addImage(mapImgData, 'PNG', 14, 44, 162, 150);

      // 2) 우측 타임라인 이미지
      const timelineImgData = timelineCanvas.toDataURL('image/png');
      doc.setFillColor(248, 250, 252);
      doc.rect(184, 42, 101, 154, 'F');
      doc.rect(184, 42, 101, 154, 'S');
      
      // 타임라인 이미지 가로/세로 비율 맞추어 삽입
      const timelineWidth = 97;
      const timelineHeight = 150;
      doc.addImage(timelineImgData, 'PNG', 186, 44, timelineWidth, timelineHeight);

      // 푸터 브랜딩
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(148, 163, 184); // slate-400
      doc.text("Generated automatically by BPA PortPath System. All data rights reserved.", 15, 204);

      // 파일 다운로드 저장
      doc.save(`BPA_Route_${selectedRoute.svc || 'Detail'}.pdf`);
    } catch (error) {
      console.error("PDF export failed:", error);
      alert("PDF 리포트 생성에 실패했습니다. 콘솔 에러를 확인하세요.");
    } finally {
      setExporting(false);
    }
  };

  const rotationList = useMemo(() => {
    if (!selectedRoute || !selectedRoute.port_rotation) return [];
    return selectedRoute.port_rotation
      .split(/[,\->]+/)
      .map((name) => name.trim())
      .filter((name) => name.length > 0);
  }, [selectedRoute]);

  const proformaList = useMemo(() => {
    if (!selectedRoute || !selectedRoute.proforma) return [];
    // SEQ 순으로 정렬
    return [...selectedRoute.proforma].sort((a, b) => (a.seq || 0) - (b.seq || 0));
  }, [selectedRoute]);

  if (!selectedRoute) return null;

  return (
    <div
      className={`relative h-screen bg-slate-900/90 backdrop-blur-xl border-l border-slate-700/50 shadow-2xl flex flex-col transition-all duration-350 ease-in-out ${
        isOpen ? 'w-[380px] opacity-100' : 'w-0 opacity-0 pointer-events-none border-l-0'
      } flex-shrink-0 z-[1000]`}
    >
      {/* ── 미려한 슬림 스크롤바 스타일 인라인 엠베딩 ── */}
      <style jsx="true">{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.12);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(0, 229, 255, 0.45);
        }
      `}</style>

      {/* ── 좌측 밀착 세로형 플로팅 핸들 탭 버튼 (100% 원클릭 인터랙티브 지원) ── */}
      <button
        onClick={onToggle}
        className="absolute left-0 top-1/2 transform -translate-x-full -translate-y-1/2 w-6 h-36 bg-slate-900/95 backdrop-blur-xl border border-r-0 border-slate-700/50 rounded-l-xl text-cyan-400 hover:text-cyan-300 shadow-2xl flex flex-col items-center justify-center gap-2.5 transition-all duration-300 pointer-events-auto cursor-pointer"
        style={{ zIndex: 1001 }}
        title={isOpen ? "Close Rotation Timeline" : "Open Rotation Timeline"}
      >
        <span className="text-[8px] font-black tracking-widest uppercase [writing-mode:vertical-lr] select-none">
          {isOpen ? "COLLAPSE" : "ROTATION"}
        </span>
        <svg 
          xmlns="http://www.w3.org/2000/svg" 
          className={`h-3 w-3 transform transition-transform duration-350 ${isOpen ? 'rotate-180' : ''}`} 
          viewBox="0 0 20 20" 
          fill="currentColor"
        >
          <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
      </button>

      {/* ── 상단 헤더 영역 ── */}
      <div className="p-5 border-b border-slate-800/80 flex items-center justify-between flex-shrink-0">
        <div className="flex flex-col">
          <span className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider">Rotation Details</span>
          <h2 className="text-base font-bold text-slate-100 truncate max-w-[200px]" title={selectedRoute.route_name}>
            {selectedRoute.route_name || 'No Name'}
          </h2>
          <span className="text-xs text-slate-400 mt-0.5">Svc: <strong className="text-slate-200">{selectedRoute.svc || 'N/A'}</strong></span>
        </div>
        <div className="flex items-center gap-2">
          {/* 📥 PDF 엑스포트 액션 버튼 */}
          <button
            onClick={handleExportPDF}
            disabled={exporting}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all duration-200 flex items-center gap-1.5 ${
              exporting
                ? 'bg-slate-800 text-slate-500 border-slate-700 cursor-not-allowed'
                : 'bg-cyan-950/40 text-cyan-400 border-cyan-500/30 hover:bg-cyan-900/40 hover:border-cyan-400 hover:text-white cursor-pointer'
            }`}
            title="Download PDF Report"
          >
            {exporting ? (
              <>
                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-cyan-400"></div>
                <span>Exporting...</span>
              </>
            ) : (
              <>
                <span>📥</span>
                <span>Export PDF</span>
              </>
            )}
          </button>
          
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 text-slate-300 hover:text-slate-100 transition-all duration-300"
            title="Close Panel"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── 중단 스펙 상세 카드 (PDF 스펙 레이아웃과 100% 싱크) ── */}
      <div className="px-5 py-4 bg-slate-950/20 border-b border-slate-800/60 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs flex-shrink-0">
        <div className="p-2 rounded-lg bg-slate-800/20 border border-slate-800 flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500 uppercase font-semibold">Frequency</span>
          <span className="font-bold text-slate-300">{selectedRoute.frequency || 'Weekly'}</span>
        </div>
        <div className="p-2 rounded-lg bg-slate-800/20 border border-slate-800 flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500 uppercase font-semibold">Carriers</span>
          <span className="font-bold text-slate-300 truncate" title={selectedRoute.carriers}>{selectedRoute.carriers || 'N/A'}</span>
        </div>
        <div className="p-2 rounded-lg bg-slate-800/20 border border-slate-800 flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500 uppercase font-semibold">Vessel / TEU</span>
          <span className="font-bold text-slate-300 truncate" title={selectedRoute.ships}>{selectedRoute.ships || 'N/A'}</span>
        </div>
        <div className="p-2 rounded-lg bg-slate-800/20 border border-slate-800 flex flex-col gap-0.5">
          <span className="text-[10px] text-slate-500 uppercase font-semibold">Duration</span>
          <span className="font-bold text-slate-300">{selectedRoute.duration ? `${selectedRoute.duration} Days` : 'N/A'}</span>
        </div>
      </div>

      {/* ── 하단 타임라인 스크롤 영역 (h-screen 높이에 완벽하게 FIT) ── */}
      <div id="timeline-scroll-container" className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
          <span>📍</span> Port Rotation Timeline
        </h3>

        <div className="relative border-l-2 border-slate-800 pl-5 ml-2.5 space-y-6">
          {rotationList.map((portName, idx) => {
            const isBusan = portName.toLowerCase().includes('busan');
            // 부산항 기항 차수(seq)를 정확히 계산하여 해당 차수의 proforma 정보만 매핑
            const busanCount = isBusan 
              ? rotationList.slice(0, idx + 1).filter(p => p.toLowerCase().includes('busan')).length 
              : 0;
            const matchedProforma = isBusan 
              ? proformaList.filter(prof => prof.seq === busanCount) 
              : [];

            return (
              <div key={`${portName}-${idx}`} className="relative">
                {/* 타임라인 노드 불릿 */}
                <div
                  className={`absolute -left-[31px] top-1.5 w-[20px] h-[20px] rounded-full border-4 flex items-center justify-center text-[9px] font-black shadow-lg ${
                    isBusan
                      ? 'bg-emerald-500 border-slate-900 text-white animate-pulse'
                      : idx === 0 || idx === rotationList.length - 1
                      ? 'bg-orange-500 border-slate-900 text-white'
                      : 'bg-slate-700 border-slate-900 text-slate-300'
                  }`}
                  style={{ width: '20px', height: '20px' }}
                >
                  {isBusan ? '★' : idx + 1}
                </div>

                {/* 기항지 명칭 카드 */}
                <div
                  className={`p-3.5 rounded-xl border transition-all duration-300 ${
                    isBusan
                      ? 'bg-emerald-950/20 border-emerald-500/25 hover:border-emerald-500/40 shadow-md shadow-emerald-950/10'
                      : 'bg-slate-800/30 border-slate-800 hover:border-slate-700/50 hover:bg-slate-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`font-bold text-sm ${
                        isBusan ? 'text-emerald-400' : 'text-slate-200'
                      }`}
                    >
                      {portName}
                    </span>
                    {isBusan && (
                      <span className="bg-emerald-500/10 text-emerald-400 text-[9px] font-bold px-2 py-0.5 rounded-full border border-emerald-500/20">
                        Busan Port
                      </span>
                    )}
                  </div>

                  {/* 🚢 기항지별 터미널 Proforma 정보 연동 카드 (PDF와 100% 매칭) */}
                  {matchedProforma.length > 0 && (
                    <div className={`mt-3 pt-3 border-t space-y-2 ${isBusan ? 'border-emerald-500/10' : 'border-slate-700/50'}`}>
                      {matchedProforma.map((prof, pIdx) => (
                        <div
                          key={`prof-${pIdx}`}
                          className={`border rounded-lg p-2.5 space-y-1.5 text-xs ${
                            isBusan
                              ? 'bg-emerald-950/30 border-emerald-500/15 text-slate-300'
                              : 'bg-slate-900/40 border-slate-700/60 text-slate-300'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className={`font-bold flex items-center gap-1 ${isBusan ? 'text-emerald-300' : 'text-cyan-400'}`}>
                              🏢 Terminal: {prof.terminal_name}
                            </span>
                            <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 rounded">
                              Seq: {prof.seq}
                            </span>
                          </div>
                          
                          <div className="grid grid-cols-1 gap-1 text-[11px] text-slate-400">
                            <div>
                              📦 Weekly Throughput: <strong className="text-slate-200">{prof.wtp || '-'} TEU</strong>
                            </div>
                            <div>
                              📅 Schedule: <strong className="text-slate-200">{prof.sch || '-'}</strong>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RotationTimeline;
