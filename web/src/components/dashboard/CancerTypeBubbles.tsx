'use client';

import * as React from 'react';
import Link from 'next/link';
import { LandscapeStat } from '@/lib/api';

interface CancerTypeBubblesProps {
  stats: LandscapeStat[];
}

// Mapping of category names to slugs for consistent URL generation
const CATEGORY_SLUG_MAP: Record<string, string> = {
  'Cutaneous melanoma': 'cutaneous-melanoma',
  'Cutaneous melanoma with Brain/CNS metastasis': 'cutaneous-melanoma-with-brain-cns-metastasis',
  'Uveal Melanoma': 'uveal-melanoma',
  'Mucosal Melanoma': 'mucosal-melanoma',
  'Acral Melanoma': 'acral-melanoma',
  'Basal Cell Carcinoma': 'basal-cell-carcinoma',
  'Merkel Cell Carcinoma': 'merkel-cell-carcinoma',
  'Cutaneous Squamous Cell Carcinoma': 'cutaneous-squamous-cell-carcinoma',
};

// Helper function to create URL-friendly slug from category name
function categoryToSlug(category: string): string {
  return CATEGORY_SLUG_MAP[category] || category
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '');
}

// Calculate bubble size based on trial count (bubble_size = recruiting + active + not yet recruiting)
function calculateBubbleSize(
  trialCount: number,
  maxTrialCount: number,
  screenWidth: number
): number {
  // Calculate size proportionally based on trial count
  const ratio = maxTrialCount > 0 ? trialCount / maxTrialCount : 0;
  
  // Define min and max sizes based on screen width with better breakpoints
  let minSize: number;
  let maxSize: number;
  
  if (screenWidth < 640) {
    // Small mobile (phones)
    minSize = 70;
    maxSize = 140;
  } else if (screenWidth < 768) {
    // Large mobile
    minSize = 80;
    maxSize = 160;
  } else if (screenWidth < 1024) {
    // Tablet
    minSize = 90;
    maxSize = 180;
  } else if (screenWidth < 1440) {
    // Small desktop/laptop
    minSize = 110;
    maxSize = 220;
  } else {
    // Large desktop
    minSize = 130;
    maxSize = 280;
  }
  
  // Calculate size with a minimum threshold to ensure smaller bubbles are still visible
  // Use sqrt for better visual scaling (area proportional to value)
  return Math.max(minSize, minSize + (maxSize - minSize) * Math.sqrt(ratio));
}

// Get consistent blue gradient for all bubbles using website color theme (lighter, aesthetic tone)
function getUniformGradient(): string {
  // Using lighter, softer blue tones for a modern, clean aesthetic
  return 'from-[#60A5FA] via-[#3B82F6] to-[#2563EB]';
}

// Format cancer type name for display
function formatCancerTypeName(name: string, maxLength: number = 25): React.ReactNode {
  if (name.length > maxLength) {
    const words = name.split(' ');
    const midPoint = Math.ceil(words.length / 2);
    const firstLine = words.slice(0, midPoint).join(' ');
    const secondLine = words.slice(midPoint).join(' ');
    return (
      <>
        <span>{firstLine}</span>
        <br />
        <span>{secondLine}</span>
      </>
    );
  }
  return name;
}

// Seeded random number generator for consistent positioning
function seededRandom(seed: number): number {
  const x = Math.sin(seed++) * 10000;
  return x - Math.floor(x);
}

// Calculate tightly packed positions for bubbles using improved circle packing
function generateRandomPositions(
  bubbles: Array<{ name: string; size: number }>,
  containerWidth: number,
  containerHeight: number
): Array<{ x: number; y: number }> {
  const positions: Array<{ x: number; y: number; radius: number }> = [];
  const centerX = containerWidth / 2;
  const centerY = containerHeight / 2;
  
  bubbles.forEach((bubble, index) => {
    const radius = bubble.size / 2;
    const seed = bubble.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) + index * 1000;
    
    if (index === 0) {
      // Place first (largest) bubble near center
      positions.push({ x: centerX, y: centerY, radius });
    } else {
      // Try to place bubble touching existing bubbles, closest to center
      let bestPos = { x: centerX, y: centerY };
      let bestDistance = Infinity;
      let placed = false;
      
      // Try placing next to each existing bubble
      for (let i = 0; i < positions.length; i++) {
        const existingPos = positions[i];
        const angleStep = Math.PI / 6; // Try 12 positions around each bubble
        
        for (let angle = 0; angle < Math.PI * 2; angle += angleStep) {
          // Calculate position touching the existing bubble
          const distance = existingPos.radius + radius;
          const x = existingPos.x + distance * Math.cos(angle);
          const y = existingPos.y + distance * Math.sin(angle);
          
          // Check if position is within bounds
          if (x - radius < 0 || x + radius > containerWidth || 
              y - radius < 0 || y + radius > containerHeight) {
            continue;
          }
          
          // Check for overlaps with other bubbles
          let hasOverlap = false;
          for (let j = 0; j < positions.length; j++) {
            if (j === i) continue;
            const pos = positions[j];
            const dist = Math.sqrt(Math.pow(x - pos.x, 2) + Math.pow(y - pos.y, 2));
            if (dist < radius + pos.radius - 1) {
              hasOverlap = true;
              break;
            }
          }
          
          if (!hasOverlap) {
            // Calculate distance to center
            const distToCenter = Math.sqrt(Math.pow(x - centerX, 2) + Math.pow(y - centerY, 2));
            
            // Prefer positions closer to center
            if (distToCenter < bestDistance) {
              bestDistance = distToCenter;
              bestPos = { x, y };
              placed = true;
            }
          }
        }
      }
      
      // If no position found, try spiral placement from center
      if (!placed) {
        const spiralRadius = radius;
        const spiralStep = radius / 2;
        const angleStep = Math.PI / 8;
        
        for (let r = spiralRadius; r < Math.max(containerWidth, containerHeight); r += spiralStep) {
          for (let angle = 0; angle < Math.PI * 2; angle += angleStep) {
            const x = centerX + r * Math.cos(angle + seededRandom(seed) * angleStep);
            const y = centerY + r * Math.sin(angle + seededRandom(seed + 1) * angleStep);
            
            if (x - radius < 0 || x + radius > containerWidth || 
                y - radius < 0 || y + radius > containerHeight) {
              continue;
            }
            
            let hasOverlap = false;
            for (const pos of positions) {
              const dist = Math.sqrt(Math.pow(x - pos.x, 2) + Math.pow(y - pos.y, 2));
              if (dist < radius + pos.radius - 1) {
                hasOverlap = true;
                break;
              }
            }
            
            if (!hasOverlap) {
              bestPos = { x, y };
              placed = true;
              break;
            }
          }
          if (placed) break;
        }
      }
      
      positions.push({ x: bestPos.x, y: bestPos.y, radius });
    }
  });
  
  return positions.map(({ x, y }) => ({ x, y }));
}

export function CancerTypeBubbles({ stats }: CancerTypeBubblesProps) {
  const [screenWidth, setScreenWidth] = React.useState(1440);
  const [screenHeight, setScreenHeight] = React.useState(900);
  const [isMobile, setIsMobile] = React.useState(false);

  React.useEffect(() => {
    const updateScreenSize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      setScreenWidth(width);
      setScreenHeight(height);
      setIsMobile(width < 768);
    };
    
    updateScreenSize();
    window.addEventListener('resize', updateScreenSize);
    return () => window.removeEventListener('resize', updateScreenSize);
  }, []);

  // Handle empty stats
  if (!stats || stats.length === 0) {
    return (
      <div className="w-full flex items-center justify-center py-8">
        <p className="text-sm text-gray-500">No cancer type data available</p>
      </div>
    );
  }

  // Sort by bubble size (largest first) - bubble_size is sum of RECRUITING, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING
  const sortedStats = [...stats].sort((a, b) => b.bubble_size - a.bubble_size);
  
  const maxBubbleSize = Math.max(...stats.map(s => s.bubble_size), 1);
  const uniformGradient = getUniformGradient();

  // Mobile layout: vertical stack (for screens < 768px)
  if (isMobile) {
    return (
      <div className="w-full flex flex-col items-center gap-3 py-4 px-2 overflow-y-auto">
        {sortedStats.map((stat) => {
          const size = calculateBubbleSize(stat.bubble_size, maxBubbleSize, screenWidth);
          return (
            <Link
              key={stat.cancer_type}
              href={`/dashboard/${categoryToSlug(stat.cancer_type)}/disease-landscape`}
              className="group cursor-pointer transition-all duration-300 hover:scale-105"
            >
              <div
                className={`rounded-full bg-gradient-to-br ${uniformGradient} shadow-2xl transition-all duration-300 group-hover:shadow-3xl flex items-center justify-center border-2 border-white/40 backdrop-blur-sm`}
                style={{
                  width: `${size}px`,
                  height: `${size}px`,
                }}
              >
                <div className="text-white font-bold text-center px-3">
                  <div className="text-sm leading-tight drop-shadow-lg">
                    {formatCancerTypeName(stat.cancer_type, 18)}
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    );
  }

  // Desktop/Tablet layout: tightly packed bubble arrangement
  // Calculate container dimensions to fit all bubbles within viewport
  // Account for header + title section + padding
  const headerSpace = 64;
  const titleSpace = screenWidth < 1024 ? 100 : 130;
  const bottomPadding = 40;
  const sidePadding = screenWidth < 1024 ? 40 : 80;
  
  // Calculate available space with proper bounds
  const availableHeight = Math.max(
    400, 
    Math.min(900, screenHeight - headerSpace - titleSpace - bottomPadding)
  );
  const availableWidth = Math.max(
    600, 
    Math.min(1200, screenWidth - sidePadding)
  );
  
  // Calculate sizes for all bubbles
  const bubblesWithSizes = sortedStats.map((stat) => ({
    name: stat.cancer_type,
    size: calculateBubbleSize(stat.bubble_size, maxBubbleSize, screenWidth),
    stat,
  }));
  
  // Calculate total bubble area for tight packing (use 60% density for better packing)
  const totalBubbleArea = bubblesWithSizes.reduce((sum, b) => sum + Math.PI * Math.pow(b.size / 2, 2), 0);
  const containerArea = availableWidth * availableHeight;
  
  // Scale bubbles for tighter packing (aim for 60% density)
  let scaleFactor = 1;
  if (totalBubbleArea > containerArea * 0.6) {
    scaleFactor = Math.sqrt((containerArea * 0.6) / totalBubbleArea);
  }
  
  // Apply scale factor to bubble sizes
  const scaledBubbles = bubblesWithSizes.map(b => ({
    ...b,
    size: Math.max(70, b.size * scaleFactor) // Minimum size of 70px for readability
  }));
  
  // Generate tightly packed positions
  const positions = generateRandomPositions(
    scaledBubbles,
    availableWidth,
    availableHeight
  );
  
  // Calculate the actual bounding box of packed bubbles for a tighter container
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  positions.forEach((pos, i) => {
    const r = scaledBubbles[i].size / 2;
    minX = Math.min(minX, pos.x - r);
    maxX = Math.max(maxX, pos.x + r);
    minY = Math.min(minY, pos.y - r);
    maxY = Math.max(maxY, pos.y + r);
  });
  
  // Adjust positions to center the packed group
  const offsetX = (availableWidth - (maxX - minX)) / 2 - minX;
  const offsetY = (availableHeight - (maxY - minY)) / 2 - minY;
  const centeredPositions = positions.map(pos => ({
    x: pos.x + offsetX,
    y: pos.y + offsetY
  }));
  
  return (
    <div className="w-full flex items-center justify-center py-2 px-2 overflow-hidden">
      <div 
        className="relative mx-auto" 
        style={{ 
          width: `${availableWidth}px`,
          height: `${availableHeight}px`,
          maxWidth: '100%',
          maxHeight: '100%',
        }}
      >
        {scaledBubbles.map((bubble, index) => {
          const position = centeredPositions[index];
          // Calculate font size based on bubble size
          const fontSize = Math.max(10, Math.min(16, bubble.size / 10));
          
          return (
            <Link
              key={bubble.stat.cancer_type}
              href={`/dashboard/${categoryToSlug(bubble.stat.cancer_type)}/disease-landscape`}
              className="absolute group cursor-pointer transition-all duration-300 hover:scale-110 hover:z-20"
              style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
                transform: 'translate(-50%, -50%)',
              }}
            >
              <div
                className={`rounded-full bg-gradient-to-br ${uniformGradient} shadow-xl transition-all duration-300 group-hover:shadow-3xl flex items-center justify-center border-2 border-white/40 backdrop-blur-sm`}
                style={{
                  width: `${bubble.size}px`,
                  height: `${bubble.size}px`,
                }}
              >
                <div className="text-white font-semibold text-center px-2" style={{ fontSize: `${fontSize}px` }}>
                  <div className="leading-tight drop-shadow-md">
                    {formatCancerTypeName(bubble.stat.cancer_type, screenWidth < 1024 ? 18 : 22)}
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
