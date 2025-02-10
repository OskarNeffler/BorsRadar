import React, { useState, useEffect } from "react";
import { Header, Dashboard, CategoryInput, ChartSection } from "./components";

const App = () => {
  const [incomeCategories, setIncomeCategories] = useState([]);
  const [spendingCategories, setSpendingCategories] = useState([]);
  const [totalIncome, setTotalIncome] = useState(0);
  const [totalExpenses, setTotalExpenses] = useState(0);
  const [totalSavings, setTotalSavings] = useState(0);

  useEffect(() => {
    setTotalIncome(
      incomeCategories.reduce(
        (sum, cat) => sum + (parseFloat(cat.amount) || 0),
        0
      )
    );
    setTotalExpenses(
      spendingCategories.reduce(
        (sum, cat) => sum + (parseFloat(cat.amount) || 0),
        0
      )
    );
    setTotalSavings(totalIncome - totalExpenses);
  }, [incomeCategories, spendingCategories]);

  return (
    <div className="min-h-screen bg-gray-100">
      <Header />
      <div className="container mx-auto p-6">
        <Dashboard
          totalIncome={totalIncome}
          totalExpenses={totalExpenses}
          totalSavings={totalSavings}
        />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <CategoryInput
            title="Income"
            categories={incomeCategories}
            setCategories={setIncomeCategories}
          />
          <CategoryInput
            title="Expenses"
            categories={spendingCategories}
            setCategories={setSpendingCategories}
          />
          <ChartSection
            incomeCategories={incomeCategories}
            spendingCategories={spendingCategories}
          />
        </div>
      </div>
    </div>
  );
};

export default App;
