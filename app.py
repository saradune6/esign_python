import io
import tempfile
import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import letter
from PIL import Image

st.set_page_config(page_title="In-House eSign Streamlit App", layout="wide")
st.title(" In-House eSign with Streamlit")

# Sidebar: Upload PDF document
doc_file = st.sidebar.file_uploader("Upload PDF document", type=["pdf"])

if doc_file:
    # Read PDF bytes and load reader
    pdf_bytes = doc_file.read()
    reader = PdfReader(io.BytesIO(pdf_bytes))
    num_pages = len(reader.pages)
    if num_pages == 0:
        st.error("Uploaded PDF has no pages. Please upload a valid PDF.")
    else:
        # Initialize session state for positions
        if 'positions' not in st.session_state:
            st.session_state.positions = {}

        # Page selection and position sliders
        st.sidebar.markdown("---")
        st.sidebar.subheader("📍 Set Signature Position per Page")
        page_idx = st.sidebar.selectbox("Select Page#", list(range(1, num_pages + 1)))
        x_perc = st.sidebar.slider("Horizontal position (%)", 0.0, 1.0, 0.5, step=0.01, key=f"x_{page_idx}")
        y_perc = st.sidebar.slider("Vertical position (%)", 0.0, 1.0, 0.1, step=0.01, key=f"y_{page_idx}")
        if st.sidebar.button("Save Position for This Page", key=f"save_{page_idx}"):
            st.session_state.positions[str(page_idx)] = (x_perc, y_perc)
            st.sidebar.success(f"Position saved for page {page_idx}")

        # Display saved positions
        st.sidebar.markdown("---")
        st.sidebar.subheader(" Saved Positions")
        for p, coords in st.session_state.positions.items():
            st.sidebar.write(f"Page {p}: x={coords[0]*100:.0f}%, y={coords[1]*100:.0f}%")

        # Canvas for signature capture
        st.sidebar.markdown("---")
        st.sidebar.subheader(" Draw / Touch Signature")
        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 0, 0)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=200,
            width=500,
            drawing_mode="freedraw",
            key="signature_canvas"
        )

        if canvas_result.image_data is not None:
            # Convert canvas to PIL image
            sig_arr = canvas_result.image_data
            sig_img = Image.fromarray(sig_arr.astype('uint8'), mode="RGBA")
            # Trim whitespace
            sig_bbox = sig_img.getbbox()
            if sig_bbox:
                sig_img = sig_img.crop(sig_bbox)

            # Show preview
            st.subheader("Signature Preview")
            st.image(sig_img, use_column_width=False)

            # Stamp PDF when user clicks
            if st.button("Sign Document to All Pages"):
                # Save signature temporarily
                sig_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                sig_img.save(sig_file.name, format="PNG")

                writer = PdfWriter()
                for page_num, page in enumerate(reader.pages):
                    # Determine position: use saved or default sliders
                    pos = st.session_state.positions.get(str(page_num + 1), (0.5, 0.1))
                    x_pos_perc, y_pos_perc = pos

                    # Create a PDF stamp
                    packet = io.BytesIO()
                    try:
                        orig_width = float(page.mediabox.width)
                        orig_height = float(page.mediabox.height)
                        page_size = (orig_width, orig_height)
                    except Exception:
                        page_size = letter

                    c = rl_canvas.Canvas(packet, pagesize=page_size)
                    sig_width = 200
                    sig_height = (sig_img.height / sig_img.width) * sig_width
                    x = x_pos_perc * page_size[0]
                    y = y_pos_perc * page_size[1]
                    c.drawImage(sig_file.name, x, y, width=sig_width, height=sig_height, mask='auto')
                    c.save()
                    packet.seek(0)

                    stamp_pdf = PdfReader(packet)
                    if stamp_pdf.pages:
                        stamp_page = stamp_pdf.pages[0]
                        page.merge_page(stamp_page)
                    writer.add_page(page)

                # Output signed PDF
                signed_bytes = io.BytesIO()
                writer.write(signed_bytes)
                signed_bytes.seek(0)

                st.success("Signed document available for download!")
                st.download_button(
                    label="📥 Download Signed PDF",
                    data=signed_bytes,
                    file_name="signed_document.pdf",
                    mime="application/pdf"
                )
