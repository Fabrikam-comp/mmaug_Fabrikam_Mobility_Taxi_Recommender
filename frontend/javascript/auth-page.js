// Runs on login.html and signup.html.
// The button's data-mode ("login" or "signup") decides which Microsoft page opens.
(async function () {
    const button = document.getElementById("authBtn");
    const message = document.getElementById("authMsg");
    const mode = button.dataset.mode;

    const account = await Auth.init();

    // Already logged in: go straight to the logged-in page.
    if (account) {
        window.location.replace("app.html");
        return;
    }

    button.addEventListener("click", async () => {
        message.textContent = "";

        const problem = Auth.setupProblem();
        if (problem) {
            message.textContent = problem;
            return;
        }

        button.disabled = true;
        try {
            if (mode === "signup") {
                await Auth.signUp();
            } else {
                await Auth.signIn();
            }
        } catch (error) {
            console.error(error);
            button.disabled = false;
            message.textContent = "Something went wrong. Please try again.";
        }
    });
})();