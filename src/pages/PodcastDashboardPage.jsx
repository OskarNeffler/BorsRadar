// src/pages/PodcastDashboardPage.jsx
import { useLoaderData, useNavigation } from "react-router-dom";
import PodcastDashboard from "../components/PodcastDashboard";
import { podcastLoader } from "../loaders/podcastLoader";

// Använd podcastLoader från separat fil för att hämta podcast-data
export const podcastDashboardLoader = podcastLoader;

const PodcastDashboardPage = () => {
  const { podcastData, error } = useLoaderData();
  const navigation = useNavigation();

  const isLoading = navigation.state === "loading";

  return (
    <div className="dashboard">
      {isLoading ? (
        <div className="grid-sm">
          <p>Laddar dashboard...</p>
        </div>
      ) : error ? (
        <div className="grid-sm">
          <p>{error}</p>
        </div>
      ) : (
        <PodcastDashboard initialData={podcastData} />
      )}
    </div>
  );
};

export default PodcastDashboardPage;
