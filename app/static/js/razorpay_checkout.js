// Opens Razorpay Checkout (TEST mode) for an order the server already created.
// The browser only passes Razorpay's signed result back; the server verifies it.
(function () {
  var cfg = document.getElementById("rzp-config");
  var button = document.getElementById("pay-button");
  var errorBox = document.getElementById("pay-error");
  if (!cfg || !button) { return; }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  var completed = false;
  button.addEventListener("click", function () {
    if (typeof window.Razorpay === "undefined") {
      showError("Razorpay could not be loaded. Check your internet connection and try again.");
      return;
    }
    var options = {
      key: cfg.dataset.key,
      order_id: cfg.dataset.orderId,
      amount: cfg.dataset.amount,
      currency: cfg.dataset.currency,
      name: "Vidyamarga",
      description: cfg.dataset.description,
      prefill: { name: cfg.dataset.name, email: cfg.dataset.email },
      theme: { color: "#1d2a5b" },
      handler: function (response) {
        completed = true;
        document.getElementById("razorpay_payment_id").value = response.razorpay_payment_id;
        document.getElementById("razorpay_order_id").value = response.razorpay_order_id;
        document.getElementById("razorpay_signature").value = response.razorpay_signature;
        document.getElementById("verify-form").submit();
      },
      modal: {
        ondismiss: function () { if (!completed) { document.getElementById("cancel-form").submit(); } }
      }
    };
    var checkout = new window.Razorpay(options);
    checkout.on("payment.failed", function () {
      showError("The payment failed. You can try again.");
    });
    checkout.open();
  });
})();
