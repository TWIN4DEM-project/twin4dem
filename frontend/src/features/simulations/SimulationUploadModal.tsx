import { type FormEvent, useEffect, useRef, useState } from "react";
import "./SimulationUploadModal.scss";
import axios from "axios";
import { useNavigate } from "react-router";
import { createSimulationFromBatch } from "@/features/simulations/hooks.ts";

type SimulationUploadModalProps = {
  isOpen: boolean;
  onClose: () => void;
  refetch: () => void;
};

type ErrorState = {
  hasError: boolean;
  details: string | null;
};

export default function SimulationUploadModal({
  isOpen,
  onClose,
  refetch,
}: SimulationUploadModalProps) {
  const modalRef = useRef<HTMLDialogElement | null>(null);
  const [errorState, setErrorState] = useState<ErrorState>({
    hasError: false,
    details: null,
  });
  const navigate = useNavigate();

  useEffect(() => {
    if (modalRef.current === null) return;
    if (isOpen) {
      modalRef.current.showModal();
    } else {
      modalRef.current.close();
    }
  }, [isOpen]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    const formData = new FormData(e.target as HTMLFormElement);
    try {
      const simulation = await createSimulationFromBatch(formData);
      refetch();
      navigate(`/simulations/${simulation.id}`);
      modalRef.current?.close();
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const errorDetails = error.response?.data?.detail;
        setErrorState({ hasError: true, details: errorDetails });
      } else {
        throw e;
      }
    }
  }

  return (
    <dialog ref={modalRef} onClose={onClose} closedby="none" className="modal">
      <form
        onSubmit={handleSubmit}
        encType="multipart/form-data"
        className="modal-form"
        onChange={() => setErrorState({ hasError: false, details: null })}
      >
        <div>
          <h1>Create Simulation</h1>
          <p>Upload aggrandisement batch file</p>
        </div>

        <div>
          <input type="file" name="file" required accept="application/zip" />
          <p hidden={!errorState}>
            ⚠️ The file you have uploaded is not valid, please make sure it matches the
            required format.
          </p>
          {errorState.details && <p>Reason: {errorState.details}</p>}
          <div className="button-container">
            <button type="submit" className="button--primary button">
              Create Simulation
            </button>
            <button type="button" className="button--outline button" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </form>
    </dialog>
  );
}
