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
  nctFilter?: string;
  sponsorFilter?: string;
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

export function TrialDataTable({ data, showAbstractId = false, hideNctId = false, nctFilter = '', sponsorFilter = '' }: TrialDataTableProps) {
  const [globalFilter] = useState('');

  // Flatten trials with multiple arms
  const flattenedData = useMemo(() => {
    const flattened = flattenTrials(data);
    
    // Apply NCT filter if provided
    let filtered = flattened;
    if (nctFilter.trim()) {
      filtered = filtered.filter(trial => 
        trial.nct_id?.toLowerCase().includes(nctFilter.toLowerCase())
      );
    }
    
    // Apply sponsor filter if provided
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
    
    return filtered;
  }, [data, nctFilter, sponsorFilter]);

  const columns: ColumnDef<Trial>[] = [
    ...(!hideNctId ? [{
      accessorKey: 'nct_id' as const,
      header: 'TRIAL ID NCT',
      cell: ({ row }: { row: { getValue: (key: string) => unknown; original: Trial } }) => {
        const nctId = row.getValue('nct_id') as string;
        if (!nctId) {
          return <span className="text-muted-foreground text-xs text-left">—</span>;
        }
        return (
          <Link
            href={`/trial/nct/${nctId}`}
            className="inline-flex items-center px-2.5 py-1 rounded-md text-primary font-medium text-xs text-left transition-all duration-200 border border-transparent hover:border-primary/30 hover:bg-blue-50 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-1"
            style={{ color: '#1A73E8' }}
          >
            {nctId}
          </Link>
        );
      },
    }] : []),
    ...(showAbstractId ? [{
      accessorKey: 'abstract_id' as const,
      header: 'ABSTRACT/PUBLICATION ID',
      cell: ({ row }: { row: { getValue: (key: string) => unknown; original: Trial } }) => {
        const trial = row.original;
        const abstractId = trial.abstract_id;
        const publicationName = trial.publication_name;
        const isPublication = trial.type === 'publication';
        
        // For publications, show publication_name if available, otherwise fall back to abstract_id
        // For abstracts, show abstract_id
        const displayValue = (isPublication && publicationName) ? publicationName : abstractId;
        
        if (!displayValue) {
          return <span className="text-muted-foreground text-xs text-left">—</span>;
        }
        
        // Use abstract_id for the link (it's the identifier)
        const linkId = abstractId || displayValue;
        
        return (
          <Link
            href={`/trial/abstract/${linkId}`}
            className="inline-flex items-center px-2.5 py-1 rounded-md text-primary font-medium text-xs text-left transition-all duration-200 border border-transparent hover:border-primary/30 hover:bg-blue-50 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:ring-offset-1"
            style={{ color: '#1A73E8' }}
            title={abstractId || displayValue}
          >
            <span className="max-w-[500px] truncate">{displayValue}</span>
          </Link>
        );
      },
    }] : []),
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
    {
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
    },
  ];

  const table = useReactTable({
    data: flattenedData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    globalFilterFn: 'includesString',
    state: {
      globalFilter,
    },
    initialState: {
      pagination: {
        pageSize: 25,
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
    </div>
  );
}
