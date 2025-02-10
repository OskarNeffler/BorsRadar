import React from "react";
import { Link } from "react-router-dom";

const Header = () => {
  return (
    <header className="bg-blue-600 text-white py-4">
      <nav className="container mx-auto flex justify-between">
        <h1 className="text-2xl font-bold">BudgetBuddy</h1>
        <ul className="flex space-x-4">
          <li>
            <Link to="/" className="hover:underline">
              Hem
            </Link>
          </li>
          <li>
            <Link to="/income" className="hover:underline">
              Inkomster
            </Link>
          </li>
          <li>
            <Link to="/expenses" className="hover:underline">
              Utgifter
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
};

export default Header;
