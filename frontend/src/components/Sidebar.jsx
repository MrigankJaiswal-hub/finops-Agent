import React from "react";
import { NavLink } from "react-router-dom";

const linkCls = ({ isActive }) =>
  `block px-3 py-2 rounded-md ${
    isActive ? "bg-blue-800" : "hover:bg-blue-700"
  }`;

const Sidebar = () => {
  const links = [
    { to: "/", label: "Dashboard" },
    { to: "/ai", label: "AI Insights" },
    { to: "/clients", label: "Clients" },
    { to: "/upload", label: "Upload Data" },
    { to: "/actions", label: "Actions Log" },
    { to: "/admin", label: "Admin" },
  ];

  return (
    <aside className="w-56 bg-blue-600 text-white flex flex-col py-6">
      <h2 className="text-center text-xl font-semibold mb-6">Menu</h2>
      <nav className="flex flex-col space-y-3 px-4">
        {links.map(({ to, label }) => (
          <NavLink key={to} to={to} className={linkCls}>
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};

export default Sidebar;