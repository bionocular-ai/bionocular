'use client';

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from '@tanstack/react-table';
import Link from 'next/link';
import { useState, useMemo } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Trial } from '@/lib/api';

interface TrialDataTableProps {
  data: Trial[];
  showAbstractId?: boolean;
  hideNctId?: boolean;
  /** When true, only show ABSTRACT/PUBLICATION ID and ARM ID columns and hide pagination. */
  compact?: boolean;
  nctFilter?: string;
  sponsorFilter?: string;
  drugFilter?: string;
  category?: string;
  armNameFilter?: string;
  trialNameFilter?: string;
  armTypeFilter?: string;
  lineOfTherapyFilter?: string;
}

// Flatten trials that have multiple arms into separate rows
function flattenTrials(trials: Trial[]): Trial[] {
  const flattened: Trial[] = [];
  
  for (const trial of trials) {
    // If trial has arms array, create one row per arm
    if (trial.arms && trial.arms.length > 0) {
      for (const arm of trial.arms) {
        flattened.push({
          ...trial,
          arm_name: arm.arm_name,
          generic_name: arm.generic_name,
        });
      }
    } else {
      // Single row trial (no arms or already flattened)
      flattened.push(trial);
    }
  }
  
  return flattened;
}

export function TrialDataTable({ 
  data, 
  showAbstractId = false, 
  hideNctId = false,
  compact = false,
  nctFilter = '', 
  sponsorFilter = '',
  drugFilter = '',
  armNameFilter = '',
  trialNameFilter = '',
  armTypeFilter = '',
  lineOfTherapyFilter = '',
  category = '',
}: TrialDataTableProps) {
  const [globalFilter] = useState('');

  // Flatten trials with multiple arms
  const flattenedData = useMemo(() => {
    const flattened = flattenTrials(data);
    
    // Apply all filters
    let filtered = flattened;
    
    // NCT filter
    if (nctFilter.trim()) {
      filtered = filtered.filter(trial => 
        trial.nct_id?.toLowerCase().includes(nctFilter.toLowerCase())
      );
    }
    
    // Sponsor filter
    if (sponsorFilter) {
      filtered = filtered.filter(trial => {
        const hasSponsor = trial.sponsor && trial.sponsor.trim() !== '';
        if (sponsorFilter === 'industry') {
          return hasSponsor; // Industry = has sponsor value
        } else if (sponsorFilter === 'non-industry') {
          return !hasSponsor; // Non-Industry = no sponsor value
        }
        return true; // 'all' or empty = show all
      });
    }
    
    // Drug/Intervention filter (generic_name)
    if (drugFilter.trim()) {
      filtered = filtered.filter(trial => 
        trial.generic_name?.toLowerCase().includes(drugFilter.toLowerCase())
      );
    }
    
    // Arm Name/Label filter
    if (armNameFilter.trim()) {
      filtered = filtered.filter(trial => 
        trial.arm_name?.toLowerCase().includes(armNameFilter.toLowerCase())
      );
    }
    
    // Trial Name/Acronym filter (title)
    if (trialNameFilter.trim()) {
      filtered = filtered.filter(trial => 
        trial.title?.toLowerCase().includes(trialNameFilter.toLowerCase())
      );
    }
    
    // Phase filter is handled in the parent component (therapeutic-index page)
    // No need to filter here since trials are already filtered by phase
    
    // Arm Type filter (if available in data)
    if (armTypeFilter.trim()) {
      filtered = filtered.filter(trial => {
        // Arm type might not be directly available, so we'll check arm_name or other fields
        const armName = trial.arm_name?.toLowerCase() || '';
        return armName.includes(armTypeFilter.toLowerCase());
      });
    }
    
    // Line of Therapy filter
    if (lineOfTherapyFilter && lineOfTherapyFilter !== 'all') {
      filtered = filtered.filter(() => {
        // Line of therapy is typically stored in arm attributes
        // Since we're working with flattened trials, we may need to check if this data is available
        // For now, we'll check if trial has any line of therapy information
        // This might need to be adjusted based on actual data structure
        // If the data comes from abstracts/publications, it would be in arm_results attributes
        // For now, return true to show all trials until we can access the actual field
        return true; // Placeholder - may need to access from trial.arms or trial attributes
      });
    }
    
    return filtered;
  }, [data, nctFilter, sponsorFilter, drugFilter, armNameFilter, trialNameFilter, armTypeFilter, lineOfTherapyFilter]);

  const abstractIdColumn: ColumnDef<Trial> = {
    accessorKey: 'abstract_id' as const,
    header: 'ABSTRACT/PUBLICATION ID',
    cell: ({ row }: { row: { getValue: (key: string) => unknown; original: Trial } }) => {
      const trial = row.original;
      const abstractId = trial.abstract_id;
      const publicationName = trial.publication_name;
      const isPublication = trial.type === 'publication';
      const sourceUrl = trial.source_url;
      const displayValue = (isPublication && publicationName) ? publicationName : abstractId;
      if (!displayValue) {
        return <span className="text-muted-foreground text-xs text-left">—</span>;
      }
      const isWebScraped = abstractId?.startsWith('webscrape_');
      if (isWebScraped && sourceUrl) {
        return (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-primary font-medium text-xs text-left transition-all duration-200 border border-transparent hover:border-primary/30 hover:bg-blue-50 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-1"
            style={{ color: '#1A73E8' }}
            title={`${abstractId || displayValue} (Click to view source)`}
          >
            <span className="max-w-[500px] truncate">{displayValue}</span>
            <svg className="h-3 w-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        );
      }
      const linkId = abstractId || displayValue;
      const abstractUrl = category
        ? `/trial/abstract/${linkId}?category=${category}`
        : `/trial/abstract/${linkId}`;
      return (
        <Link
          href={abstractUrl}
          className="inline-flex items-center px-2.5 py-1 rounded-md text-primary font-medium text-xs text-left transition-all duration-200 border border-transparent hover:border-primary/30 hover:bg-blue-50 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-1"
          style={{ color: '#1A73E8' }}
          title={abstractId || displayValue}
        >
          <span className="max-w-[500px] truncate">{displayValue}</span>
        </Link>
      );
    },
  };

  const armIdColumn: ColumnDef<Trial> = {
    accessorKey: 'arm_name',
    header: 'ARM ID',
    cell: ({ row }) => {
      const armName = row.getValue('arm_name') as string;
      return (
        <div className="max-w-[150px] truncate text-xs text-left" title={armName}>
          {armName || <span className="text-muted-foreground">—</span>}
        </div>
      );
    },
  };

  const columns: ColumnDef<Trial>[] = compact
    ? [
        ...(showAbstractId ? [abstractIdColumn] : []),
        armIdColumn,
      ]
    : [
        ...(!hideNctId ? [{
          accessorKey: 'nct_id' as const,
          header: 'TRIAL ID NCT',
          cell: ({ row }: { row: { getValue: (key: string) => unknown; original: Trial } }) => {
            const nctId = row.getValue('nct_id') as string;
            if (!nctId) {
              return <span className="text-muted-foreground text-xs text-left">—</span>;
            }
            const nctUrl = category
              ? `/trial/nct/${nctId}?category=${category}`
              : `/trial/nct/${nctId}`;
            return (
              <Link
                href={nctUrl}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-primary font-medium text-xs text-left transition-all duration-200 border border-transparent hover:border-primary/30 hover:bg-blue-50 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-1"
                style={{ color: '#1A73E8' }}
              >
                {nctId}
              </Link>
            );
          },
        }] : []),
        ...(showAbstractId ? [abstractIdColumn] : []),
        {
          accessorKey: 'sponsor',
          header: 'SPONSOR',
          cell: ({ row }) => {
            const sponsor = row.getValue('sponsor') as string;
            return (
              <div className="max-w-[200px] truncate text-xs text-left" title={sponsor}>
                {sponsor || <span className="text-muted-foreground">—</span>}
              </div>
            );
          },
        },
        {
          accessorKey: 'generic_name',
          header: 'GENERIC NAME',
          cell: ({ row }) => {
            const genericName = row.getValue('generic_name') as string;
            return (
              <div className="max-w-[200px] truncate text-xs text-left" title={genericName}>
                {genericName || <span className="text-muted-foreground">—</span>}
              </div>
            );
          },
        },
        {
          accessorKey: 'cancer_type',
          header: 'CANCER TYPE',
          cell: ({ row }) => {
            const cancerType = row.getValue('cancer_type') as string;
            return (
              <div className="max-w-[200px] truncate text-xs text-left" title={cancerType}>
                {cancerType || <span className="text-muted-foreground">—</span>}
              </div>
            );
          },
        },
        armIdColumn,
      ];

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: flattenedData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    ...(compact ? {} : { getPaginationRowModel: getPaginationRowModel() }),
    globalFilterFn: 'includesString',
    state: {
      globalFilter,
    },
    initialState: {
      pagination: {
        pageSize: compact ? flattenedData.length : 25,
      },
    },
  });

  return (
    <div className="space-y-4">
      <div className="w-full">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="border-b hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead 
                    key={header.id}
                    className="text-[10px] uppercase tracking-wider font-semibold text-gray-500 bg-white h-10 text-left px-4"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && 'selected'}
                  className="border-b hover:bg-muted/50"
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell 
                      key={cell.id}
                      className="py-2 px-4 h-12 text-left text-xs"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-xs text-muted-foreground"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {!compact && (
        <div className="flex items-center justify-between">
          <div className="text-xs text-muted-foreground">
            Page {table.getState().pagination.pageIndex + 1} of{' '}
            {table.getPageCount()} ({flattenedData.length} items)
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
              variant="outline"
              size="sm"
              className="text-xs h-8"
            >
              &lt;&lt;
            </Button>
            <Button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              variant="outline"
              size="sm"
              className="text-xs h-8"
            >
              &lt;
            </Button>
            <Button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              variant="outline"
              size="sm"
              className="text-xs h-8"
            >
              &gt;
            </Button>
            <Button
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
              variant="outline"
              size="sm"
              className="text-xs h-8"
            >
              &gt;&gt;
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
