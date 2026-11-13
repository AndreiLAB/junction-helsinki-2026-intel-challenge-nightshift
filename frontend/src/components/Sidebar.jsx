import React, { useState } from 'react';
import { LayoutGrid, Camera, Sliders, History, Cpu, Settings, HelpCircle, ChevronRight } from 'lucide-react';

export default function Sidebar({ activeTab, onSelectTab, wsConnected }) {
  const [currentTab, setCurrentTab] = useState(activeTab || 'overview');

  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutGrid },
    { id: 'inspection', label: 'Inspection', icon: Camera },
    { id: 'rules', label: 'Sorting rules', icon: Sliders },
    { id: 'history', label: 'Cycle history', icon: History },
    { id: 'hardware', label: 'Hardware', icon: Cpu },
  ];

  const handleSelect = (id) => {
    setCurrentTab(id);
    if (onSelectTab) onSelectTab(id);
  };

  return (
    <aside className="w-full lg:w-[216px] bg-[#0e131a] border-b lg:border-b-0 lg:border-r border-[#26313e] flex flex-col justify-between shrink-0 p-4 select-none">
      <div>
        {/* Brand Header */}
        <div className="flex items-center space-x-3 mb-8">
          <div className="w-7 h-7 rounded-[7px] bg-[#55dbb1] flex items-center justify-center text-[#0b0f14] shadow-md shadow-[#55dbb1]/20 shrink-0">
            <LayoutGrid className="w-4 h-4 text-[#0b0f14]" />
          </div>
          <div>
            <div className="font-bold text-[13px] tracking-wide text-[#edf2f7] leading-tight">
              PHYSICAL AI
            </div>
            <div className="font-medium text-[10px] text-[#8e9bae] tracking-widest leading-none mt-0.5">
              STUDIO
            </div>
          </div>
        </div>

        {/* Section: WORKSPACE */}
        <div className="text-[10px] font-semibold text-[#8e9bae] tracking-wider uppercase mb-3 px-1">
          WORKSPACE
        </div>

        {/* Nav list */}
        <nav className="space-y-1 mb-8">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-[13px] transition-all relative font-medium ${
                  isActive
                    ? 'bg-[#18212c] text-[#edf2f7]'
                    : 'text-[#8e9bae] hover:text-[#edf2f7] hover:bg-[#18212c]/50'
                }`}
              >
                {isActive && (
                  <div className="absolute left-0 top-1.5 bottom-1.5 w-[3px] bg-[#55dbb1] rounded-r" />
                )}
                <Icon className={`w-4 h-4 ${isActive ? 'text-[#55dbb1]' : 'text-[#8e9bae]'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Divider */}
        <div className="h-px bg-[#26313e] my-5" />

        {/* CONNECTED CELL */}
        <div className="px-1 mb-6">
          <div className="text-[10px] font-semibold text-[#8e9bae] tracking-wider uppercase mb-2.5">
            CONNECTED CELL
          </div>
          <div className="flex items-center space-x-2 mb-1">
            <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-[#55dbb1] animate-pulse' : 'bg-amber-400'}`} />
            <span className="text-[12px] font-medium text-[#b5c0ce]">SO-ARM101</span>
          </div>
          <div className="text-[11px] text-[#8e9bae] mb-2.5">
            RealSense D415 + QHD
          </div>
          <div className="inline-flex items-center bg-[#15352e] border border-[#55dbb1]/30 px-2.5 py-1 rounded-[5px]">
            <span className="text-[11px] font-medium text-[#55dbb1]">
              {wsConnected ? 'Edge connected' : 'Connecting...'}
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Area */}
      <div>
        {/* Event Card */}
        <div className="bg-[#121922] border border-[#26313e] rounded-lg p-3 mb-5">
          <div className="text-[10px] font-semibold text-[#55dbb1] tracking-wider uppercase mb-1">
            JUNCTION 2026
          </div>
          <div className="text-[12px] font-medium text-[#edf2f7] leading-snug">
            Autonomous inspection
          </div>
          <div className="text-[10px] text-[#8e9bae] mt-0.5">
            Intel Physical AI Challenge
          </div>
        </div>

        {/* Bottom Nav items */}
        <div className="space-y-1 pt-2 border-t border-[#26313e]/60">
          <button className="w-full flex items-center space-x-3 px-2 py-1.5 text-[12px] text-[#8e9bae] hover:text-[#edf2f7] transition-colors rounded">
            <Settings className="w-4 h-4 text-[#8e9bae]" />
            <span>Settings</span>
          </button>
          <button className="w-full flex items-center space-x-3 px-2 py-1.5 text-[12px] text-[#8e9bae] hover:text-[#edf2f7] transition-colors rounded">
            <HelpCircle className="w-4 h-4 text-[#8e9bae]" />
            <span>Help & documentation</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
