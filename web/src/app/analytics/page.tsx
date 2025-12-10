'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import HeadToHeadChart from '@/components/charts/HeadToHeadChart';
import { transformHeadToHeadData } from '@/lib/chart-transformers';
import { HeadToHeadDataPoint, EfficacyMetric, EFFICACY_METRICS, TrialDataFile } from '@/types/analytics';

// ============================================================================
// Demo Data - Simulating real clinical trial data structure
// ============================================================================

const DEMO_DATA = {
  total_abstracts: 25,
  total_arms: 40,
  total_attributes_extracted: 800,
  average_confidence: 0.75,
  abstracts: [
    // Nivolumab + Ipilimumab trials
    {
      abstract_id: 'ASCO_2022_9500',
      total_arms: 2,
      total_attributes_extracted: 40,
      overall_confidence: 0.8,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Nivolumab + Ipilimumab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2022', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9500', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT01844505', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Nivolumab + Ipilimumab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 72.1, confidence: 0.85, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 11.5, confidence: 0.85, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 314, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    {
      abstract_id: 'ESMO_2023_1001',
      total_arms: 1,
      total_attributes_extracted: 30,
      overall_confidence: 0.75,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Nivolumab + Ipilimumab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ESMO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2023', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '1001', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT02714218', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Nivolumab + Ipilimumab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 49.2, confidence: 0.8, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 12.1, confidence: 0.8, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 458, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Pembrolizumab trials
    {
      abstract_id: 'ASCO_2021_9501',
      total_arms: 1,
      total_attributes_extracted: 28,
      overall_confidence: 0.82,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Pembrolizumab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2021', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9501', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT02362594', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Pembrolizumab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 32.7, confidence: 0.85, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 8.4, confidence: 0.85, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 556, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    {
      abstract_id: 'ASCO_2023_LBA9500',
      total_arms: 1,
      total_attributes_extracted: 32,
      overall_confidence: 0.78,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Pembrolizumab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2023', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: 'LBA9500', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT03142334', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Pembrolizumab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 38.2, confidence: 0.8, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 9.8, confidence: 0.8, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 612, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Dabrafenib + Trametinib
    {
      abstract_id: 'ASCO_2020_9502',
      total_arms: 1,
      total_attributes_extracted: 35,
      overall_confidence: 0.79,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Dabrafenib + Trametinib',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2020', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9502', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT01682083', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Dabrafenib + Trametinib', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 25.9, confidence: 0.85, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 14.9, confidence: 0.85, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 352, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    {
      abstract_id: 'ESMO_2022_850',
      total_arms: 1,
      total_attributes_extracted: 30,
      overall_confidence: 0.76,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Dabrafenib + Trametinib',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ESMO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2022', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '850', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT02967692', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Dabrafenib + Trametinib', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 28.4, confidence: 0.8, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 13.2, confidence: 0.8, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 298, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Ipilimumab monotherapy
    {
      abstract_id: 'ASCO_2020_9600',
      total_arms: 1,
      total_attributes_extracted: 28,
      overall_confidence: 0.72,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Ipilimumab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2020', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9600', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT00094653', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Ipilimumab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 19.9, confidence: 0.85, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 2.9, confidence: 0.85, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 250, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    {
      abstract_id: 'ESMO_2021_920',
      total_arms: 1,
      total_attributes_extracted: 26,
      overall_confidence: 0.7,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Ipilimumab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ESMO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2021', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '920', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT01515189', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Ipilimumab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 53.0, confidence: 0.75, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 3.1, confidence: 0.75, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 180, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Encorafenib + Binimetinib
    {
      abstract_id: 'ASCO_2022_9700',
      total_arms: 1,
      total_attributes_extracted: 32,
      overall_confidence: 0.77,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Encorafenib + Binimetinib',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2022', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9700', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT01909453', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Encorafenib + Binimetinib', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 33.6, confidence: 0.82, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 14.9, confidence: 0.82, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 192, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Vemurafenib
    {
      abstract_id: 'ASCO_2021_9650',
      total_arms: 1,
      total_attributes_extracted: 30,
      overall_confidence: 0.74,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Vemurafenib',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2021', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9650', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT01006980', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Vemurafenib', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 13.6, confidence: 0.8, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 6.9, confidence: 0.8, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 337, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // T-VEC (Talimogene laherparepvec)
    {
      abstract_id: 'ESMO_2020_780',
      total_arms: 1,
      total_attributes_extracted: 28,
      overall_confidence: 0.71,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Talimogene Laherparepvec',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ESMO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2020', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '780', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT00769704', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Talimogene Laherparepvec', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 23.3, confidence: 0.78, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 8.2, confidence: 0.78, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 295, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Investigational treatment - Lifileucel
    {
      abstract_id: 'ASCO_2024_9505',
      total_arms: 1,
      total_attributes_extracted: 34,
      overall_confidence: 0.8,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Lifileucel',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2024', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9505', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT02360579', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE2', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Lifileucel', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 14.0, confidence: 0.75, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 4.2, confidence: 0.75, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 66, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Investigational treatment - Novel combination
    {
      abstract_id: 'ASCO_2024_LBA9510',
      total_arms: 1,
      total_attributes_extracted: 30,
      overall_confidence: 0.73,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Fianlimab + Cemiplimab',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2024', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: 'LBA9510', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT05352672', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Fianlimab + Cemiplimab', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 'NR', confidence: 0.6, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 13.7, confidence: 0.8, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 235, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
    // Placebo/SOC comparators
    {
      abstract_id: 'ASCO_2020_9503',
      total_arms: 1,
      total_attributes_extracted: 25,
      overall_confidence: 0.7,
      errors: [],
      warnings: [],
      arm_results: {
        arm_1: {
          arm_id: 'arm_1',
          arm_name: 'Dacarbazine',
          attributes: {
            'AttributeType.CONFERENCE': { value: 'ASCO', confidence: 1.0, source: 'file_path' },
            'AttributeType.PUBLISHED_YEAR': { value: '2020', confidence: 1.0, source: 'file_path' },
            'AttributeType.ABSTRACT_NUMBER': { value: '9503', confidence: 0.9, source: 'extraction' },
            'AttributeType.NCT_NUMBER': { value: 'NCT00324155', confidence: 0.9, source: 'api' },
            'AttributeType.CLINICAL_TRIAL_PHASE': { value: 'PHASE3', confidence: 0.9, source: 'api' },
            'AttributeType.GENERIC_NAME': { value: 'Dacarbazine', confidence: 0.9, source: 'extraction' },
            'AttributeType.MEDIAN_OS': { value: 10.3, confidence: 0.8, source: 'extraction' },
            'AttributeType.MEDIAN_PFS': { value: 1.6, confidence: 0.8, source: 'extraction' },
            'AttributeType.NUMBER_OF_PATIENTS': { value: 263, confidence: 0.9, source: 'extraction' },
          },
        },
      },
    },
  ],
};

// ============================================================================
// Component
// ============================================================================

export default function AnalyticsPage() {
  const [selectedMetric, setSelectedMetric] = useState<EfficacyMetric>('MEDIAN_OS');
  const [showReferenceLine, setShowReferenceLine] = useState(true);

  // Transform data for the chart
  const chartData = useMemo<HeadToHeadDataPoint[]>(() => {
    return transformHeadToHeadData(DEMO_DATA as TrialDataFile, {
      targetMetric: selectedMetric,
      minTrialCount: 1,
    });
  }, [selectedMetric]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-sky-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      {/* Header */}
      <header className="sticky top-0 z-10 backdrop-blur-xl bg-white/80 dark:bg-slate-900/80 border-b border-slate-200 dark:border-slate-800">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                Clinical Trial Analytics
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                Head-to-head efficacy comparison across treatment arms
              </p>
            </div>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white transition-colors"
            >
              ← Back to Dashboard
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {/* Controls */}
        <div className="mb-8 flex flex-wrap items-center gap-6 p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
          {/* Metric Selector */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Y Variable
            </label>
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value as EfficacyMetric)}
              className="px-4 py-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all min-w-[200px]"
            >
              {Object.entries(EFFICACY_METRICS).map(([key, config]) => (
                <option key={key} value={key}>
                  {config.label} ({config.unit || 'ratio'})
                </option>
              ))}
            </select>
          </div>

          {/* Reference Line Toggle */}
          <div className="flex items-center gap-3">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={showReferenceLine}
                onChange={(e) => setShowReferenceLine(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-sky-500 dark:peer-focus:ring-sky-600 rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-sky-500"></div>
              <span className="ms-3 text-sm font-medium text-slate-700 dark:text-slate-300">
                Show Average Line
              </span>
            </label>
          </div>

          {/* Data Summary */}
          <div className="ml-auto flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="text-slate-600 dark:text-slate-300">
                {chartData.length} treatments
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-sky-500"></span>
              <span className="text-slate-600 dark:text-slate-300">
                {chartData.reduce((sum, d) => sum + d.trialCount, 0)} trials
              </span>
            </div>
          </div>
        </div>

        {/* Chart */}
        <HeadToHeadChart
          data={chartData}
          metric={selectedMetric}
          title={`${EFFICACY_METRICS[selectedMetric].description} by Drug/Intervention`}
          description={`Comparing ${EFFICACY_METRICS[selectedMetric].label} across melanoma treatment arms. Bars represent weighted averages; scatter points show individual trial results.`}
          height={520}
          showReferenceLine={showReferenceLine}
          showLegend={true}
        />

        {/* Data Table Preview */}
        <div className="mt-8 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
            <h3 className="font-semibold text-slate-900 dark:text-white">
              Data Summary
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50">
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Treatment
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Avg {EFFICACY_METRICS[selectedMetric].unit}
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Range
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Trials
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Patients
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {chartData.map((row, idx) => (
                  <tr
                    key={idx}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="px-6 py-4 font-medium text-slate-900 dark:text-white">
                      {row.treatmentName}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          row.approvalStatus === 'Approved'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                            : 'bg-violet-100 text-violet-800 dark:bg-violet-900/50 dark:text-violet-300'
                        }`}
                      >
                        {row.approvalStatus}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-slate-700 dark:text-slate-300">
                      {row.averageValue.toFixed(1)}
                    </td>
                    <td className="px-6 py-4 text-right font-mono text-slate-500 dark:text-slate-400">
                      {row.minValue.toFixed(1)} – {row.maxValue.toFixed(1)}
                    </td>
                    <td className="px-6 py-4 text-right text-slate-700 dark:text-slate-300">
                      {row.trialCount}
                    </td>
                    <td className="px-6 py-4 text-right text-slate-700 dark:text-slate-300">
                      {row.totalPatients > 0 ? `n=${row.totalPatients}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

