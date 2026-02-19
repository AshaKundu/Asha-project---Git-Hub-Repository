import os
import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    try:
        API_BASE_URL = st.secrets["API_BASE_URL"]
    except Exception:
        API_BASE_URL = None

if not API_BASE_URL:
    st.error("API_BASE_URL is not set. Configure it in environment variables or Streamlit secrets.")
    st.stop()
CATEGORIES = ["smartphone", "laptop", "smart_tv", "speaker"]

st.set_page_config(page_title="Smart Shop MVP", layout="wide")

st.title("Smart Shop AI Assistant")
st.caption("Recommendations, price comparison, and review insights powered by AI.")

if "active_product" not in st.session_state:
    st.session_state.active_product = None

if "chat" not in st.session_state:
    st.session_state.chat = []

if "active_user" not in st.session_state:
    st.session_state.active_user = None


def api_get(path, params=None):
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def api_post(path, payload):
    response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=20)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text
        raise requests.HTTPError(f"{exc} | {detail}") from exc
    return response.json()


def api_put(path, payload):
    response = requests.put(f"{API_BASE_URL}{path}", json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


with st.sidebar:
    st.subheader("User profile")
    users = api_get("/users")
    user_options = {f"{user['name']} ({user['id']})": user for user in users}
    selected_label = st.selectbox("Active user", list(user_options.keys()))
    st.session_state.active_user = user_options[selected_label]

    with st.expander("Create user"):
        with st.form("create_user_form"):
            new_id = st.text_input("User ID")
            new_name = st.text_input("Name")
            new_categories = st.multiselect("Preferred categories", CATEGORIES)
            new_budget_min = st.number_input("Budget min", min_value=0.0, value=0.0)
            new_budget_max = st.number_input("Budget max", min_value=0.0, value=0.0)
            submit = st.form_submit_button("Create")
            if submit:
                if not new_id or not new_name:
                    st.error("User ID and Name are required.")
                else:
                    try:
                        api_post(
                            "/users",
                            {
                                "id": new_id,
                                "name": new_name,
                                "preferred_categories": new_categories,
                                "budget_min": new_budget_min if new_budget_min > 0 else None,
                                "budget_max": new_budget_max if new_budget_max > 0 else None,
                            },
                        )
                        st.success("User created")
                        st.rerun()
                    except requests.HTTPError as exc:
                        st.error(f"Create failed: {exc}")

    with st.expander("Edit active user"):
        active_user = st.session_state.active_user
        with st.form("edit_user_form"):
            name = st.text_input("Name", value=active_user["name"])
            preferred = st.multiselect(
                "Preferred categories",
                CATEGORIES,
                default=active_user.get("preferred_categories", []),
            )
            budget_min = st.number_input(
                "Budget min",
                min_value=0.0,
                value=float(active_user.get("budget_min") or 0.0),
            )
            budget_max = st.number_input(
                "Budget max",
                min_value=0.0,
                value=float(active_user.get("budget_max") or 0.0),
            )
            save = st.form_submit_button("Save")
            if save:
                api_put(
                    f"/users/{active_user['id']}",
                    {
                        "name": name,
                        "preferred_categories": preferred,
                        "budget_min": budget_min if budget_min > 0 else None,
                        "budget_max": budget_max if budget_max > 0 else None,
                    },
                )
                st.success("Profile updated")
                st.rerun()

    st.subheader("Search")
    query = st.text_input("Search products")
    in_stock_only = st.checkbox("In stock only", value=True)
    search_trigger = st.button("Search")

if search_trigger:
    results = api_get(
        "/products",
        params={
            "query": query,
            "in_stock_only": str(in_stock_only).lower(),
            "user_id": st.session_state.active_user["id"],
        },
    )
else:
    results = api_get("/recommendations", params={"user_id": st.session_state.active_user["id"]})

col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("Products")
    if not results:
        st.info(
            "No products match the preferred categories or budget. Update preferences/budget to see results."
        )
    else:
        for item in results:
            product = item.get("product", item)
            price = product["price"]
            with st.container(border=True):
                st.markdown(f"**{product['name']}**")
                st.caption(f"{product['brand']} · {product['category']}")
                st.markdown(f"Price: ${price:.2f}")
                if item.get("reason"):
                    st.caption(f"Reason: {item['reason']}")
                if st.button(f"Select {product['id']}", key=product["id"]):
                    st.session_state.active_product = product
                    api_post(
                        "/users/events",
                        {
                            "user_id": st.session_state.active_user["id"],
                            "product_id": product["id"],
                            "event_type": "view",
                        },
                    )

with col2:
    st.subheader("Assistant")
    active = st.session_state.active_product
    if active:
        st.markdown(f"**{active['name']}** ({active['id']})")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Add to wishlist"):
                api_post(
                    "/users/events",
                    {
                        "user_id": st.session_state.active_user["id"],
                        "product_id": active["id"],
                        "event_type": "wishlist",
                    },
                )
                st.success("Wishlist saved")
        with col_b:
            if st.button("Record purchase"):
                api_post(
                    "/users/events",
                    {
                        "user_id": st.session_state.active_user["id"],
                        "product_id": active["id"],
                        "event_type": "purchase",
                    },
                )
                st.success("Purchase recorded")

        summary = api_get("/reviews/summary", params={"product_id": active["id"]})
        review_list = api_get("/reviews", params={"product_id": active["id"]})
        comparison = api_get("/price-compare", params={"product_id": active["id"]})
        policy = api_get("/policy", params={"product_id": active["id"]})
        warranty = api_get(
            "/policy",
            params={"product_id": active["id"], "policy_type": "warranty"},
        )

        st.markdown("### Insights")
        st.write(
            f"Average rating {summary['average_rating']} from {summary['total_reviews']} reviews."
        )
        if summary.get("summary_text"):
            st.write(summary["summary_text"])
        if summary.get("themes"):
            st.write("Themes:", ", ".join([item["word"] for item in summary["themes"]]))

        st.markdown("### Recent Reviews")
        if review_list:
            for review in review_list:
                st.write(f"⭐ {review['rating']} — {review['text']}")
        else:
            st.write("No reviews available.")

        st.markdown("### Price Comparison")
        st.write(
            f"${comparison['min']} - ${comparison['max']} (avg ${comparison['avg']})"
        )
        if comparison.get("cheaper"):
            st.write(
                "Cheaper picks:",
                ", ".join([item["name"] for item in comparison["cheaper"]]),
            )

        st.markdown("### Policy Automation")
        st.write(policy["description"])
        st.write("Timeframe:", f"{policy['timeframe']} days")
        st.write("Conditions:", " · ".join(policy["conditions"]))

        if warranty:
            st.markdown("### Warranty Policy")
            st.write(warranty["description"])
            st.write("Timeframe:", f"{warranty['timeframe']} days")
            st.write("Conditions:", " · ".join(warranty["conditions"]))
    else:
        st.info("Select a product to view insights and pricing.")

st.divider()

st.subheader("Chat")
for item in st.session_state.chat:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])

message = st.chat_input("Ask about price comparisons, reviews, or recommendations")
if message:
    st.session_state.chat.append({"role": "user", "content": message})
    payload = {
        "message": message,
        "product_id": st.session_state.active_product["id"] if st.session_state.active_product else None,
        "user_id": st.session_state.active_user["id"] if st.session_state.active_user else None,
    }
    response = api_post("/chat", payload)
    st.session_state.chat.append({"role": "assistant", "content": response["reply"]})
    extra_lines = []
    if response.get("payload"):
        if response["payload"].get("recommendations"):
            extra_lines.append("Recommendations:")
            for item in response["payload"]["recommendations"]:
                product = item.get("product", {})
                reason = item.get("reason")
                line = f"- {product.get('name')} (${product.get('price')})"
                if reason:
                    line += f" — {reason}"
                extra_lines.append(line)
        if response["payload"].get("cheapest"):
            extra_lines.append("Cheapest options:")
            for item in response["payload"]["cheapest"]:
                extra_lines.append(f"- {item['name']} (${item['price']})")
        if response["payload"].get("results"):
            extra_lines.append("Matches:")
            for item in response["payload"]["results"]:
                product = item.get("product", {})
                extra_lines.append(f"- {product.get('name')} (${product.get('price')})")
        if response["payload"].get("comparison_pair"):
            pair = response["payload"]["comparison_pair"]
            left = pair.get("left", {})
            right = pair.get("right", {})
            extra_lines.append("Comparison:")
            extra_lines.append(
                f"- {left.get('name')} (${left.get('price')}) [{left.get('category')}]"
            )
            if left.get("review_summary"):
                extra_lines.append(
                    f"  • Reviews: {left['review_summary']['average_rating']} avg from {left['review_summary']['total_reviews']} reviews"
                )
            if left.get("policy"):
                extra_lines.append(f"  • Policy: {left['policy']['description']} ({left['policy']['timeframe']} days)")
            extra_lines.append(
                f"- {right.get('name')} (${right.get('price')}) [{right.get('category')}]"
            )
            if right.get("review_summary"):
                extra_lines.append(
                    f"  • Reviews: {right['review_summary']['average_rating']} avg from {right['review_summary']['total_reviews']} reviews"
                )
            if right.get("policy"):
                extra_lines.append(f"  • Policy: {right['policy']['description']} ({right['policy']['timeframe']} days)")
        if response["payload"].get("reviews"):
            extra_lines.append("Recent reviews:")
            for item in response["payload"]["reviews"]:
                extra_lines.append(f"- ⭐ {item['rating']} — {item['text']}")
    if extra_lines:
        st.session_state.chat.append({"role": "assistant", "content": "\n".join(extra_lines)})
    st.rerun()
