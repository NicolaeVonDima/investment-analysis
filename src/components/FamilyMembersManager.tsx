import React, { useState, useEffect } from 'react';
import { FamilyMember } from '../types';
import { formatCurrency } from '../utils/formatters';

interface FamilyMembersManagerProps {
  familyMembers: FamilyMember[];
  onUpdate: (members: FamilyMember[]) => void;
}

export default function FamilyMembersManager({ familyMembers, onUpdate }: FamilyMembersManagerProps) {
  const [localMembers, setLocalMembers] = useState<FamilyMember[]>(familyMembers);
  const [isEditing, setIsEditing] = useState<{ [key: string]: boolean }>({});

  useEffect(() => {
    // Sort by display_order to ensure correct order
    const sorted = [...familyMembers].sort((a, b) => (a.displayOrder || 0) - (b.displayOrder || 0));
    setLocalMembers(sorted);
  }, [familyMembers]);

  const totalInvestment = localMembers.reduce((sum, member) => sum + member.amount, 0);

  const handleNameChange = (id: string, name: string) => {
    const updated = localMembers.map(m => 
      m.id === id ? { ...m, name: name.trim() } : m
    );
    setLocalMembers(updated);
    onUpdate(updated);
  };

  const handleAmountChange = (id: string, amount: number) => {
    const updated = localMembers.map(m => 
      m.id === id ? { ...m, amount: Math.max(0, amount) } : m
    );
    setLocalMembers(updated);
    onUpdate(updated);
  };

  const handleColorChange = (id: string, color: string) => {
    const updated = localMembers.map(m => 
      m.id === id ? { ...m, color } : m
    );
    setLocalMembers(updated);
    onUpdate(updated);
  };

  const handleAddMember = () => {
    const newId = `member-${Date.now()}`;
    // Get the highest display_order and add 1
    const maxOrder = Math.max(...localMembers.map(m => m.displayOrder || 0), -1);
    // Default colors for new members
    const defaultColors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#6366F1', '#818CF8'];
    const colorIndex = (maxOrder + 1) % defaultColors.length;
    const newMember: FamilyMember = {
      id: newId,
      name: '',
      amount: 0,
      displayOrder: maxOrder + 1,
      color: defaultColors[colorIndex]
    };
    const updated = [...localMembers, newMember];
    setLocalMembers(updated);
    setIsEditing({ ...isEditing, [newId]: true });
    onUpdate(updated);
  };

  const handleRemoveMember = (id: string) => {
    // First member (by display_order 0 or default-1 id) cannot be removed
    const firstMember = localMembers.find(m => m.displayOrder === 0) || localMembers.find(m => m.id === 'default-1') || localMembers[0];
    if (localMembers.length <= 1 || firstMember.id === id) {
      if (firstMember.id === id) {
        alert('The first portfolio owner cannot be removed');
      } else {
        alert('At least one family member is required');
      }
      return;
    }
    const updated = localMembers.filter(m => m.id !== id);
    // Reassign display_order after removal
    const reordered = updated.map((m, idx) => ({ ...m, displayOrder: idx }));
    setLocalMembers(reordered);
    onUpdate(reordered);
  };

  const handleMoveUp = (id: string) => {
    const currentIndex = localMembers.findIndex(m => m.id === id);
    if (currentIndex <= 0) return; // Already first or not found
    
    const updated = [...localMembers];
    [updated[currentIndex - 1], updated[currentIndex]] = [updated[currentIndex], updated[currentIndex - 1]];
    // Reassign display_order
    const reordered = updated.map((m, idx) => ({ ...m, displayOrder: idx }));
    setLocalMembers(reordered);
    onUpdate(reordered);
  };

  const handleMoveDown = (id: string) => {
    const currentIndex = localMembers.findIndex(m => m.id === id);
    if (currentIndex < 0 || currentIndex >= localMembers.length - 1) return; // Already last or not found
    
    const updated = [...localMembers];
    [updated[currentIndex], updated[currentIndex + 1]] = [updated[currentIndex + 1], updated[currentIndex]];
    // Reassign display_order
    const reordered = updated.map((m, idx) => ({ ...m, displayOrder: idx }));
    setLocalMembers(reordered);
    onUpdate(reordered);
  };

  const getMemberPercentage = (amount: number): number => {
    if (totalInvestment === 0) return 0;
    return (amount / totalInvestment) * 100;
  };

  // Use indigo color to match Family Total card theme
  const borderColor = '#6366F1'; // indigo-500

  return (
    <div 
      className="bg-white rounded-lg shadow-lg border-2 p-6"
      style={{ borderColor }}
    >
      <div className="flex items-center justify-between mb-4 pb-3 border-b">
        <div className="flex items-center gap-2">
          <div 
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ backgroundColor: borderColor }}
          />
          <div>
            <label className="block text-lg font-semibold text-gray-800">
              Capital Contributors
            </label>
            <p className="text-sm text-gray-600 mt-1">
              Add family members and their contribution amounts. The total will be used for all portfolios.
            </p>
          </div>
        </div>
        <button
          onClick={handleAddMember}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm font-semibold shadow-sm border-2 border-indigo-600"
        >
          + Add Member
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
        {localMembers.map((member, index) => {
          // First member is the one with displayOrder 0 or default-1 id (if no displayOrder 0 exists)
          const isFirstMember = (member.displayOrder === 0) || (member.id === 'default-1' && !localMembers.some(m => m.displayOrder === 0 && m.id !== member.id));
          const displayName = member.name.trim() || 'Owner Portfolio';
          
          // Use member's color or assign default if not set
          const defaultColors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#6366F1', '#818CF8'];
          const memberColor = member.color || defaultColors[(member.displayOrder || index) % defaultColors.length];
          
          // Convert hex to rgba with opacity for lighter background
          const hexToRgba = (hex: string, opacity: number) => {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${opacity})`;
          };

          const cardBgColor = hexToRgba(memberColor, 0.15); // Light background
          const buttonBgColor = hexToRgba(memberColor, 0.25); // Slightly darker for button

          return (
            <div 
              key={member.id} 
              className="rounded-lg shadow-md hover:shadow-lg transition-all relative overflow-hidden"
              style={{ backgroundColor: cardBgColor }}
            >
              {/* Decorative icon/pattern on right */}
              <div 
                className="absolute top-0 right-0 w-24 h-24 opacity-10 pointer-events-none"
                style={{ 
                  background: `radial-gradient(circle, ${memberColor} 0%, transparent 70%)`,
                  transform: 'translate(20%, -20%)'
                }}
              />

              {/* Content */}
              <div className="relative p-4">
                {/* Header with name */}
                <div className="mb-4">
                  <input
                    type="text"
                    value={member.name}
                    onChange={(e) => handleNameChange(member.id, e.target.value)}
                    onBlur={() => setIsEditing({ ...isEditing, [member.id]: false })}
                    onFocus={() => setIsEditing({ ...isEditing, [member.id]: true })}
                    placeholder={isFirstMember ? "Owner name" : "Member name"}
                    className="w-full px-3 py-2 bg-white/60 backdrop-blur-sm rounded-lg focus:outline-none focus:ring-2 focus:ring-white/50 text-base font-bold text-gray-800 placeholder:text-gray-500"
                  />
                  {isFirstMember && !member.name.trim() && (
                    <p className="text-xs text-gray-600 mt-1 opacity-75">Defaults to "Owner Portfolio"</p>
                  )}
                </div>

                {/* Investment Amount - Large Display */}
                <div className="mb-4">
                  <div className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2 opacity-80">
                    Investment Amount
                  </div>
                  <div className="text-3xl font-bold mb-1" style={{ color: memberColor }}>
                    {formatCurrency(member.amount)}
                  </div>
                  <div className="text-sm font-medium opacity-75" style={{ color: memberColor }}>
                    {getMemberPercentage(member.amount).toFixed(1)}% of total
                  </div>
                </div>

                {/* Amount Input */}
                <div className="mb-4">
                  <input
                    type="number"
                    value={member.amount || ''}
                    onChange={(e) => handleAmountChange(member.id, parseFloat(e.target.value) || 0)}
                    onBlur={() => setIsEditing({ ...isEditing, [member.id]: false })}
                    onFocus={() => setIsEditing({ ...isEditing, [member.id]: true })}
                    className="w-full px-3 py-2 bg-white/60 backdrop-blur-sm rounded-lg focus:outline-none focus:ring-2 focus:ring-white/50 text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    min="0"
                    step="1000"
                    placeholder="Enter amount"
                  />
                </div>

                {/* Footer with color picker and remove button */}
                <div className="flex items-center gap-2 pt-3 border-t border-white/30">
                  {/* Color Picker */}
                  <div className="flex items-center gap-1.5 flex-1">
                    <label className="text-xs font-medium text-gray-700 whitespace-nowrap opacity-80">Color:</label>
                    <input
                      type="color"
                      value={memberColor}
                      onChange={(e) => handleColorChange(member.id, e.target.value)}
                      className="w-6 h-6 rounded cursor-pointer flex-shrink-0 border border-white/50"
                      title="Pick a color for this member"
                    />
                    <input
                      type="text"
                      value={memberColor}
                      onChange={(e) => handleColorChange(member.id, e.target.value)}
                      className="flex-1 px-2 py-1 bg-white/60 backdrop-blur-sm rounded text-xs font-mono focus:outline-none focus:ring-2 focus:ring-white/50"
                      placeholder="#000000"
                      pattern="^#[0-9A-Fa-f]{6}$"
                    />
                  </div>
                  {/* Remove Button */}
                  <button
                    onClick={() => handleRemoveMember(member.id)}
                    disabled={isFirstMember}
                    className="px-3 py-1.5 text-white rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed text-xs font-semibold whitespace-nowrap hover:opacity-90"
                    style={{ 
                      backgroundColor: isFirstMember ? 'rgba(156, 163, 175, 0.5)' : 'rgba(239, 68, 68, 0.7)'
                    }}
                    title={isFirstMember ? "The first portfolio owner cannot be removed" : "Remove member"}
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="pt-4 mt-4 border-t-2 border-gray-200">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Total Investment:</span>
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-indigo-900">{formatCurrency(totalInvestment)}</span>
            <span className="text-sm text-gray-500 font-medium">({localMembers.length} {localMembers.length === 1 ? 'member' : 'members'})</span>
          </div>
        </div>
        {totalInvestment === 0 && (
          <p className="text-xs text-red-600 mt-2 font-medium">⚠️ Total investment must be greater than 0</p>
        )}
      </div>
    </div>
  );
}

