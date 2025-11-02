import React from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const ChartCard = ({ data }) => (
  <div className="bg-white p-6 rounded-xl shadow-sm">
    <h3 className="font-semibold text-lg mb-4 text-blue-700">Client Profitability</h3>
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="client" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="margin" fill="#2563eb" />
      </BarChart>
    </ResponsiveContainer>
  </div>
);

export default ChartCard;
