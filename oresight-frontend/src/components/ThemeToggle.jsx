import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function ThemeToggle({ className = '' }) {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      aria-label={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      className={`relative inline-flex items-center h-7 w-13 rounded-full p-0.5 transition-colors duration-200 cursor-pointer border ${
        isDark
          ? 'bg-[#211F1D] border-[#38352F] hover:border-[#5B7A99]'
          : 'bg-[#FAF8F3] border-[#DDD6C8] hover:border-[#6B2737]'
      } ${className}`}
    >
      {/* Background Icons */}
      <span className="absolute left-1.5 flex items-center justify-center text-[#6E695E] opacity-70">
        <Sun size={12} strokeWidth={2} />
      </span>
      <span className="absolute right-1.5 flex items-center justify-center text-[#A39C8D] opacity-70">
        <Moon size={11} strokeWidth={2} />
      </span>

      {/* Sliding Toggle Knob */}
      <span
        className={`inline-flex items-center justify-center w-5 h-5 rounded-full shadow-xs transition-transform duration-200 transform ${
          isDark
            ? 'translate-x-6 bg-[#9C4A57] text-[#EDE8DD]'
            : 'translate-x-0.5 bg-[#6B2737] text-white'
        }`}
      >
        {isDark ? (
          <Moon size={11} strokeWidth={2.2} />
        ) : (
          <Sun size={11} strokeWidth={2.2} />
        )}
      </span>
    </button>
  );
}
