// rrd imports
import { redirect } from "react-router-dom";

// library
import { toast } from "react-toastify";

// helpers

export async function logoutAction() {
  // delete the user

  toast.success("You’ve deleted your account!");
  // return redirect
  return redirect("/");
}
