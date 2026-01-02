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

// Calculate bubble size based on rank position (biggest, bigger, big, small, smaller, smallest)
// Rank 0 = central (biggest), Rank 1-2 = bigger, Rank 3-4 = big, Rank 5 = small, Rank 6 = smaller, Rank 7 = smallest
function calculateBubbleSizeByRank(
  rank: number,
  screenWidth: number
): number {
  // Size hierarchy: biggest > bigger > big > small > smaller > smallest
  const getSizeForRank = (rank: number, baseSizes: {
    biggest: number;
    bigger: number;
    big: number;
    small: number;
    smaller: number;
    smallest: number;
  }): number => {
    if (rank === 0) return baseSizes.biggest; // Central
    if (rank <= 2) return baseSizes.bigger;   // Left top, Right top
    if (rank <= 4) return baseSizes.big;       // Left middle, Right middle
    if (rank === 5) return baseSizes.small;    // Left bottom
    if (rank === 6) return baseSizes.smaller;   // Right bottom
    return baseSizes.smallest;                 // Top center (rank 7)
  };

  if (screenWidth < 640) {
    // Mobile
    return getSizeForRank(rank, {
      biggest: 140,
      bigger: 100,
      big: 85,
      small: 75,
      smaller: 70,
      smallest: 65
    });
  } else if (screenWidth < 1024) {
    // Tablet/Small laptop
    return getSizeForRank(rank, {
      biggest: 180,
      bigger: 140,
      big: 120,
      small: 105,
      smaller: 95,
      smallest: 90
    });
  } else if (screenWidth < 1440) {
    // MacBook Air / Medium laptop - further reduced to fit screen
    return getSizeForRank(rank, {
      biggest: 180,
      bigger: 140,
      big: 120,
      small: 105,
      smaller: 95,
      smallest: 90
    });
  } else {
    // Large desktop - further reduced to fit screen
    return getSizeForRank(rank, {
      biggest: 240,
      bigger: 190,
      big: 160,
      small: 140,
      smaller: 130,
      smallest: 120
    });
  }
}

// Get blue gradient based on bubble size
function getBlueGradient(bubbleSize: number, maxSize: number, isCentral: boolean = false): string {
  const ratio = maxSize > 0 ? bubbleSize / maxSize : 0;
  
  if (isCentral) {
    return 'from-[#0B3A78] via-[#1A73E8] to-[#0EA5E9]';
  }
  
  if (ratio > 0.7) {
    return 'from-[#1A73E8] via-[#4285F4] to-[#0EA5E9]';
  } else if (ratio > 0.4) {
    return 'from-[#4285F4] via-[#5BA3F5] to-[#0EA5E9]';
  } else {
    return 'from-[#5BA3F5] via-[#7BB3F6] to-[#A8D5F8]';
  }
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

// Calculate elliptical position for surrounding bubbles around the central bubble
// Uses wider horizontal radius to better utilize screen space
function getEllipticalPosition(
  index: number,
  total: number,
  horizontalRadius: number,
  verticalRadius: number
): { x: number; y: number } {
  // Distribute bubbles evenly around an ellipse
  // Start from top (270 degrees) and go clockwise
  const angleStep = 360 / total;
  const angle = (270 + (index * angleStep)) * (Math.PI / 180);
  
  // Use elliptical coordinates for better horizontal space utilization
  const x = horizontalRadius * Math.cos(angle);
  const y = verticalRadius * Math.sin(angle);
  
  return { x, y };
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

  // Sort by bubble size (largest first) - bubble_size is sum of RECRUITING, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING
  const sortedStats = [...stats].sort((a, b) => b.bubble_size - a.bubble_size);
  
  // Largest bubble goes in center (rank 0 = biggest)
  const centralStat = sortedStats[0];
  const surroundingStats = sortedStats.slice(1);
  
  const maxBubbleSize = Math.max(...stats.map(s => s.bubble_size), 1);
  const centralSize = calculateBubbleSizeByRank(0, screenWidth);

  // Mobile layout: vertical stack
  if (isMobile) {
    return (
      <div className="w-full flex flex-col items-center gap-4 py-4 px-2">
        {/* Central bubble first on mobile */}
        {centralStat && (
          <Link
            href={`/dashboard/${categoryToSlug(centralStat.cancer_type)}/disease-landscape`}
            className="group cursor-pointer transition-all duration-300 hover:scale-105"
          >
            <div
              className={`rounded-full bg-gradient-to-br ${getBlueGradient(centralStat.bubble_size, maxBubbleSize, true)} shadow-2xl transition-all duration-300 group-hover:shadow-3xl flex items-center justify-center border-2 border-white/40 backdrop-blur-sm`}
              style={{
                width: `${centralSize}px`,
                height: `${centralSize}px`,
              }}
            >
              <div className="text-white font-bold text-center px-4">
                <div className="text-base sm:text-lg leading-tight drop-shadow-lg">
                  {formatCancerTypeName(centralStat.cancer_type, 20)}
                </div>
              </div>
            </div>
          </Link>
        )}

        {/* Surrounding bubbles in grid on mobile */}
        <div className="grid grid-cols-2 gap-3 w-full max-w-sm">
          {surroundingStats.map((stat, index) => {
            const rank = index + 1; // Rank 1-7 for surrounding bubbles
            const size = calculateBubbleSizeByRank(rank, screenWidth);
            return (
              <Link
                key={stat.cancer_type}
                href={`/dashboard/${categoryToSlug(stat.cancer_type)}/disease-landscape`}
                className="group cursor-pointer transition-all duration-300 hover:scale-110 flex justify-center"
              >
                <div
                  className={`rounded-full bg-gradient-to-br ${getBlueGradient(stat.bubble_size, maxBubbleSize, false)} shadow-xl transition-all duration-300 group-hover:shadow-2xl flex items-center justify-center border-2 border-white/40 backdrop-blur-sm`}
                  style={{
                    width: `${size}px`,
                    height: `${size}px`,
                  }}
                >
                  <div className="text-white font-semibold text-center px-2">
                    <div className="text-xs leading-tight drop-shadow-md">
                      {formatCancerTypeName(stat.cancer_type, 18)}
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

  // Desktop/Tablet layout: central with circular arrangement
  // Calculate container dimensions to fit all bubbles within viewport
  // Account for header (64px) + title section (approximately 100-130px) + padding
  const headerSpace = 64; // Header height
  const titleSpace = screenWidth < 1024 ? 100 : 130; // Title section height
  const padding = 20; // Top and bottom padding
  const availableHeight = Math.max(400, screenHeight - headerSpace - titleSpace - padding);
  const availableWidth = Math.max(600, screenWidth - 40); // 20px padding on each side
  
  // Get sizes for all surrounding bubbles to calculate proper spacing
  const surroundingSizes = surroundingStats.map((_, index) => 
    calculateBubbleSizeByRank(index + 1, screenWidth)
  );
  const maxSurroundingSize = surroundingSizes.length > 0 ? Math.max(...surroundingSizes) : 0;
  
  // Calculate elliptical radii to better utilize horizontal space
  // Ensure minimum spacing between bubbles (at least 25px for separation)
  const minSpacing = 25;
  const minHorizontalRadius = (centralSize / 2) + (maxSurroundingSize / 2) + minSpacing;
  const minVerticalRadius = (centralSize / 2) + (maxSurroundingSize / 2) + minSpacing;
  
  // Calculate maximum safe radii - use more horizontal space, less vertical
  const margin = 15; // Safety margin
  const maxHorizontalRadius = Math.max(0, (availableWidth - centralSize - maxSurroundingSize) / 2 - margin);
  const maxVerticalRadius = Math.max(0, (availableHeight - centralSize - maxSurroundingSize) / 2 - margin);
  
  // Use wider horizontal radius to utilize side space better
  // Horizontal radius can be larger since we have more horizontal space
  const horizontalRadius = Math.max(
    minHorizontalRadius, 
    Math.min(maxHorizontalRadius, minHorizontalRadius + (maxHorizontalRadius - minHorizontalRadius) * 0.7)
  );
  
  // Vertical radius should be more constrained to fit on screen
  const verticalRadius = Math.max(
    minVerticalRadius,
    Math.min(maxVerticalRadius, minVerticalRadius + (maxVerticalRadius - minVerticalRadius) * 0.5)
  );
  
  // Container size should fit all bubbles including those at edges
  // Account for bubbles extending beyond the ellipse (half bubble on each side)
  const maxBubbleAtEdge = Math.max(maxSurroundingSize, centralSize);
  const containerWidth = Math.min(
    Math.ceil((horizontalRadius * 2) + maxBubbleAtEdge + margin * 2),
    availableWidth
  );
  const containerHeight = Math.min(
    Math.ceil((verticalRadius * 2) + maxBubbleAtEdge + margin * 2),
    availableHeight
  );
  
  return (
    <div className="w-full flex items-center justify-center py-2 px-2">
      <div 
        className="relative mx-auto" 
        style={{ 
          width: `${containerWidth}px`,
          height: `${containerHeight}px`,
          maxWidth: '100%',
          maxHeight: `${availableHeight}px`,
        }}
      >
        {/* Central Bubble - Largest */}
        {centralStat && (
          <Link
            href={`/dashboard/${categoryToSlug(centralStat.cancer_type)}/disease-landscape`}
            className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 group cursor-pointer transition-all duration-300 hover:scale-105 z-10"
          >
            <div
              className={`rounded-full bg-gradient-to-br ${getBlueGradient(centralStat.bubble_size, maxBubbleSize, true)} shadow-2xl transition-all duration-300 group-hover:shadow-3xl flex items-center justify-center border-4 border-white/40 backdrop-blur-sm`}
              style={{
                width: `${centralSize}px`,
                height: `${centralSize}px`,
              }}
            >
              <div className="text-white font-bold text-center px-4 sm:px-6 md:px-8">
                <div className="text-lg sm:text-xl md:text-2xl lg:text-3xl leading-tight drop-shadow-lg">
                  {formatCancerTypeName(centralStat.cancer_type, screenWidth < 1024 ? 22 : 25)}
                </div>
              </div>
            </div>
          </Link>
        )}

        {/* Surrounding bubbles in elliptical arrangement around center */}
        {surroundingStats.map((stat, index) => {
          const rank = index + 1; // Rank 1-7 for surrounding bubbles
          const size = calculateBubbleSizeByRank(rank, screenWidth);
          const position = getEllipticalPosition(
            index, 
            surroundingStats.length, 
            horizontalRadius,
            verticalRadius
          );
          
          return (
            <Link
              key={stat.cancer_type}
              href={`/dashboard/${categoryToSlug(stat.cancer_type)}/disease-landscape`}
              className="absolute group cursor-pointer transition-all duration-300 hover:scale-110"
              style={{
                left: `calc(50% + ${position.x}px)`,
                top: `calc(50% + ${position.y}px)`,
                transform: 'translate(-50%, -50%)',
              }}
            >
              <div
                className={`rounded-full bg-gradient-to-br ${getBlueGradient(stat.bubble_size, maxBubbleSize, false)} shadow-xl transition-all duration-300 group-hover:shadow-2xl flex items-center justify-center border-2 border-white/40 backdrop-blur-sm`}
                style={{
                  width: `${size}px`,
                  height: `${size}px`,
                }}
              >
                <div className="text-white font-semibold text-center px-2 sm:px-3 md:px-4">
                  <div className="text-xs sm:text-sm md:text-base leading-tight drop-shadow-md">
                    {formatCancerTypeName(stat.cancer_type, screenWidth < 1024 ? 20 : 25)}
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
