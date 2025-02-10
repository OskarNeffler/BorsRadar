import React from "react";

const Dashboard = () => {
  return (
    <div className="bg-gray-100 min-h-screen">
      <div className="container mx-auto p-6">
        <h1 className="text-4xl font-bold text-center text-blue-600">
          BudgetBuddy
        </h1>
        <p className="text-center text-gray-600 mt-2">
          Hantera dina inkomster och utgifter enkelt.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
          <div className="bg-white shadow-md rounded-lg p-4">
            <h2 className="text-xl font-bold text-gray-800">Total Inkomst</h2>
            <p className="text-green-500 font-bold text-2xl">5000 SEK</p>
          </div>
          <div className="bg-white shadow-md rounded-lg p-4">
            <h2 className="text-xl font-bold text-gray-800">Total Utgift</h2>
            <p className="text-red-500 font-bold text-2xl">2000 SEK</p>
          </div>
          <div className="bg-white shadow-md rounded-lg p-4">
            <h2 className="text-xl font-bold text-gray-800">Sparande</h2>
            <p className="text-blue-500 font-bold text-2xl">3000 SEK</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
