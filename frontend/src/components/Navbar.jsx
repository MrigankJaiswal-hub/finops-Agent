import React from "react";
import logo from "/logo.png";

const Navbar = () => (
  <nav className="flex justify-between items-center px-6 py-3 border-b bg-white shadow-sm">
    <div className="flex items-center space-x-3">
      <img src={logo} alt="FinOps+" className="w-8 h-8" />
      <h1 className="font-semibold text-lg text-blue-600">FinOps+ Agent</h1>
    </div>
    <span className="text-gray-500 text-sm">AWS + Kiros | Hackathon Prototype</span>
  </nav>
);

export default Navbar;
