import React from "react";

const Dashboard = () => {
  return (
    <div className="p-6">
      <h2 className="text-3xl font-bold mb-4">Your Budget Overview</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-4 bg-green-100 rounded-lg shadow">
          <h3 className="text-xl font-semibold">Total Income</h3>
          <p>$5,000</p>
        </div>
        <div className="p-4 bg-red-100 rounded-lg shadow">
          <h3 className="text-xl font-semibold">Total Expenses</h3>
          <p>$3,200</p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
