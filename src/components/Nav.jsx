// rrd imports
import { Form, NavLink } from "react-router-dom";

// library
import { TrashIcon } from "@heroicons/react/24/solid";

// assets
import radar_green from "../assets/radar_green.svg";

const Nav = ({ userName }) => {
  return (
    <nav>
      <NavLink to="/" aria-label="Go to home">
        <img src={radar_green} alt="" height={30} />
        <span>BörsRadar</span>
      </NavLink>
      {userName && (
        <div className="flex-sm">
          <NavLink
            to="/news"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <span>Börsnyheter</span>
          </NavLink>

          <NavLink
            to="/podcasts"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <span>Podcasts</span>
          </NavLink>

          <NavLink
            to="/related-content"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <span>Relaterat Innehåll</span>
          </NavLink>

          <NavLink
            to="/logout"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <span>Logga ut</span>
          </NavLink>

          <Form
            method="post"
            action="/logout"
            onSubmit={(event) => {
              if (!confirm("Delete user and all data?")) {
                event.preventDefault();
              }
            }}
          ></Form>
        </div>
      )}
    </nav>
  );
};
export default Nav;
