import React, { useEffect, useState } from "react";
import { RevenueSummary } from "./RevenueSummary";
import { SecureAPI } from "../lib/secureApi";

interface Property {
  id: string;
  name: string;
}

const Dashboard: React.FC = () => {
  const [properties, setProperties] = useState<Property[]>([]);
  const [selectedProperty, setSelectedProperty] = useState('');
  // The month input gives "YYYY-MM", or an empty string when cleared, which means all time
  const [selectedMonth, setSelectedMonth] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadProperties = async () => {
      try {
        const response = await SecureAPI.getProperties();
        setProperties(response.data);
        if (response.data.length > 0) {
          setSelectedProperty(response.data[0].id);
        }
      } catch (err) {
        setError('Failed to load your properties');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadProperties();
  }, []);

  const [pickedYear, pickedMonth] = selectedMonth.split('-').map(Number);
  // An empty input gives year 0. A year being typed passes through values like "0202-03", and the API only accepts 2000-2100
  const hasPeriod = pickedYear >= 2000 && pickedYear <= 2100;

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">Property Management Dashboard</h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <div className="mb-6">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
              <div>
                <h2 className="text-lg lg:text-xl font-medium text-gray-900 mb-2">Revenue Overview</h2>
                <p className="text-sm lg:text-base text-gray-600">
                  Monthly performance insights for your properties
                </p>
              </div>
              
              <div className="flex flex-col sm:flex-row gap-4">
                {/* Period Selector */}
                <div className="flex flex-col sm:items-end">
                  <label htmlFor="revenue-period" className="text-xs font-medium text-gray-700 mb-1">Period</label>
                  <div className="flex items-center gap-2">
                    {selectedMonth && (
                      <button
                        type="button"
                        onClick={() => setSelectedMonth('')}
                        className="px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm text-gray-700 whitespace-nowrap hover:bg-gray-50 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      >
                        All time
                      </button>
                    )}
                    <input
                      id="revenue-period"
                      type="month"
                      min="2000-01"
                      max="2100-12"
                      value={selectedMonth}
                      onChange={(e) => setSelectedMonth(e.target.value)}
                      className="block w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                    />
                  </div>
                </div>

                {/* Property Selector */}
                <div className="flex flex-col sm:items-end">
                  <label className="text-xs font-medium text-gray-700 mb-1">Select Property</label>
                  <select
                    value={selectedProperty}
                    onChange={(e) => setSelectedProperty(e.target.value)}
                    disabled={properties.length === 0}
                    className="block w-full sm:w-auto min-w-[200px] px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                  >
                    {properties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {loading && <div className="p-4 text-gray-500 bg-gray-50 rounded-lg">Loading your properties...</div>}
            {error && <div className="p-4 text-red-500 bg-red-50 rounded-lg">{error}</div>}
            {!loading && !error && properties.length === 0 && (
              <div className="p-4 text-gray-500 bg-gray-50 rounded-lg">No properties found for your account.</div>
            )}
            {selectedProperty && <RevenueSummary propertyId={selectedProperty} month={hasPeriod ? pickedMonth : undefined} year={hasPeriod ? pickedYear : undefined} />}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
