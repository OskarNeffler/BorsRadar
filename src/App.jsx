import { createBrowserRouter, RouterProvider } from "react-router-dom";

// Library
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

// Layouts
import Main, { mainLoader } from "./layouts/Main";

// Actions
import { logoutAction } from "./actions/logout";

// Routes
import Dashboard, { dashboardAction, dashboardLoader } from "./pages/Dashboard";
import Error from "./pages/Error";
import NewsPage from "./pages/Newspage";
import { newsLoader } from "./loaders/newsLoader";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Main />,
    loader: mainLoader,
    errorElement: <Error />,
    children: [
      {
        path: "news",
        element: <NewsPage />,
        loader: newsLoader,
        errorElement: <Error />,
      },
      {
        path: "logout",
        action: logoutAction,
      },
      {
        index: true,
        element: <Dashboard />,
        loader: dashboardLoader,
        action: dashboardAction,
        errorElement: <Error />,
      },
    ],
  },
]);

function App() {
  return (
    <div className="App">
      <RouterProvider router={router} />
      <ToastContainer />
    </div>
  );
}

export default App;
