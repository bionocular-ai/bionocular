'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface SegmentedControlOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

export interface SegmentedControlProps {
  options: SegmentedControlOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function SegmentedControl({
  options,
  value,
  onChange,
  className,
  size = 'md',
}: SegmentedControlProps) {
  const sizeClasses = {
    sm: 'h-8 text-xs px-2',
    md: 'h-9 text-sm px-3',
    lg: 'h-10 text-base px-4',
  };

  const selectedIndex = options.findIndex((opt) => opt.value === value);

  return (
    <div
      className={cn(
        'relative inline-flex items-center rounded-lg bg-slate-100 p-1 border border-slate-200 shadow-sm',
        className
      )}
      role="tablist"
    >
      {/* Animated background indicator */}
      <div
        className="absolute top-1 bottom-1 rounded-md bg-white shadow-sm transition-all duration-200 ease-out"
        style={{
          left: `${(selectedIndex * 100) / options.length}%`,
          width: `${100 / options.length}%`,
        }}
      />
      
      {options.map((option, index) => {
        const isSelected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={isSelected}
            onClick={() => onChange(option.value)}
            className={cn(
              'relative z-10 flex items-center justify-center gap-1.5 rounded-md font-medium transition-all duration-200',
              'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2',
              sizeClasses[size],
              isSelected
                ? 'text-slate-900 font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            )}
          >
            {option.icon && (
              <span className={cn(isSelected ? 'text-slate-900' : 'text-slate-500')}>
                {option.icon}
              </span>
            )}
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
