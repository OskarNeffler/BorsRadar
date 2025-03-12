import React from "react";

// Komponenten för att visa utgifter i en tabell
const Table = ({ expenses }) => {
  return (
    <div className="table">
      <table>
        <thead>
          <tr>
            {["Namn", "Belopp", "Datum"].map((i, index) => (
              <th key={index}>{i}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {expenses.map((expense) => (
            <tr key={expense.id}>
              <td>{expense.name}</td>
              <td>${expense.amount}</td>
              <td>{new Date(expense.createdAt).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
