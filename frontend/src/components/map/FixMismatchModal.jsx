import { useState, useEffect } from 'react';
import { routeService } from '../../services/api';

/**
 * 항구 매칭 오류 수정 모달.
 * Unmatched 포트명을 올바른 포트 코드에 매핑합니다.
 */
const FixMismatchModal = ({ isOpen, onClose, unmatchedPorts, allPorts, routeIdx, onFixed }) => {
  const [selectedBad, setSelectedBad] = useState('');
  const [selectedGood, setSelectedGood] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    if (unmatchedPorts.length > 0) setSelectedBad(unmatchedPorts[0]);
  }, [unmatchedPorts]);

  if (!isOpen) return null;

  const filteredPorts = allPorts
    .filter(
      (p) =>
        p.port_name.toLowerCase().includes(filterText.toLowerCase()) ||
        p.port_code.toLowerCase().includes(filterText.toLowerCase())
    )
    .slice(0, 50);

  const handleFix = async () => {
    if (!selectedBad || !selectedGood) return;
    setIsSubmitting(true);
    try {
      await routeService.fixPortMismatch(routeIdx, selectedBad, selectedGood);
      onFixed();
    } catch (e) {
      alert('Failed to fix mismatch: ' + e.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-96 max-w-full">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-[#003399]">Fix Port Mismatch</h3>
          <div className="text-xs text-gray-500 font-normal">{unmatchedPorts.length} issue(s) remaining</div>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-bold text-gray-700 mb-1">Unmatched Port Name (Typo)</label>
          <select
            className="w-full border border-gray-300 rounded p-2 text-sm"
            value={selectedBad}
            onChange={(e) => setSelectedBad(e.target.value)}
          >
            {unmatchedPorts.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        <div className="mb-6">
          <label className="block text-xs font-bold text-gray-700 mb-1">Map to Correct Port</label>
          <input
            type="text"
            placeholder="Search port..."
            className="w-full border border-gray-300 rounded p-1 text-xs mb-1"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
          />
          <select
            className="w-full border border-gray-300 rounded p-2 text-sm"
            value={selectedGood}
            onChange={(e) => setSelectedGood(e.target.value)}
            size={5}
          >
            {filteredPorts.map((p) => (
              <option key={p.port_code} value={p.port_code}>
                {p.port_name} ({p.nation_name})
              </option>
            ))}
          </select>
        </div>

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded text-sm">
            Close
          </button>
          <button
            onClick={handleFix}
            disabled={isSubmitting || !selectedGood}
            className="px-4 py-2 bg-[#003399] text-white rounded hover:bg-blue-800 text-sm disabled:opacity-50"
          >
            {isSubmitting ? 'Saving...' : 'Save & Fix'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FixMismatchModal;
