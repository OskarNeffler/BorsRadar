import React from "react";

const Header = () => {
  return (
    <header className="bg-blue-500 text-white py-4 px-6 flex justify-between">
      <h1 className="text-2xl font-bold">BudgetBuddy</h1>
      <nav>
        <ul className="flex space-x-4">
          <li>
            <a href="/" className="hover:underline">
              Home
            </a>
          </li>
          <li>
            <a href="/about" className="hover:underline">
              About
            </a>
          </li>
          <li>
            <a href="/expenses" className="hover:underline">
              Expenses
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
};

export default Header;
