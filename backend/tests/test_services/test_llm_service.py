"""Tests for LLM service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestLLMServiceGenerate:
    """Test LLM text generation."""

    @pytest.fixture
    def llm_service(self):
        """Create LLMService with mocked client."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-api-key"
            mock_settings.gemini_model = "gemini-pro"
            mock_settings.gemini_embedding_model = "embedding-001"

            with patch("app.services.llm_service.genai") as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client

                from app.services.llm_service import LLMService
                service = LLMService()
                service._mock_client = mock_client
                return service

    @pytest.mark.asyncio
    async def test_generate_returns_text(self, llm_service):
        """generate returns generated text."""
        mock_response = MagicMock()
        mock_response.text = "This is the generated response."

        llm_service._mock_client.models.generate_content.return_value = mock_response

        result = await llm_service.generate("Test prompt")

        assert result == "This is the generated response."

    @pytest.mark.asyncio
    async def test_generate_handles_none_text(self, llm_service):
        """generate returns empty string if response text is None."""
        mock_response = MagicMock()
        mock_response.text = None

        llm_service._mock_client.models.generate_content.return_value = mock_response

        result = await llm_service.generate("Test prompt")

        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_raises_on_error(self, llm_service):
        """generate raises exception on API error."""
        llm_service._mock_client.models.generate_content.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc:
            await llm_service.generate("Test prompt")

        assert "API Error" in str(exc.value)


class TestLLMServiceGenerateWithUsage:
    """Test LLM generation with usage tracking."""

    @pytest.fixture
    def llm_service(self):
        """Create LLMService with mocked client."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-api-key"
            mock_settings.gemini_model = "gemini-pro"
            mock_settings.gemini_embedding_model = "embedding-001"

            with patch("app.services.llm_service.genai") as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client

                from app.services.llm_service import LLMService
                service = LLMService()
                service._mock_client = mock_client
                return service

    @pytest.mark.asyncio
    async def test_generate_with_usage_returns_tuple(self, llm_service):
        """generate_with_usage returns tuple of text and usage."""
        mock_response = MagicMock()
        mock_response.text = "Generated text"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50

        llm_service._mock_client.models.generate_content.return_value = mock_response

        text, usage = await llm_service.generate_with_usage("Test prompt")

        assert text == "Generated text"
        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50

    @pytest.mark.asyncio
    async def test_generate_with_usage_handles_no_metadata(self, llm_service):
        """generate_with_usage returns 0 tokens if no metadata."""
        mock_response = MagicMock()
        mock_response.text = "Generated text"
        mock_response.usage_metadata = None

        llm_service._mock_client.models.generate_content.return_value = mock_response

        text, usage = await llm_service.generate_with_usage("Test prompt")

        assert text == "Generated text"
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0


class TestLLMServiceEmbeddings:
    """Test LLM embedding creation."""

    @pytest.fixture
    def llm_service(self):
        """Create LLMService with mocked client."""
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.gemini_api_key = "test-api-key"
            mock_settings.gemini_model = "gemini-pro"
            mock_settings.gemini_embedding_model = "embedding-001"

            with patch("app.services.llm_service.genai") as mock_genai:
                mock_client = MagicMock()
                mock_genai.Client.return_value = mock_client

                from app.services.llm_service import LLMService
                service = LLMService()
                service._mock_client = mock_client
                return service

    @pytest.mark.asyncio
    async def test_create_embedding_returns_vector(self, llm_service):
        """create_embedding returns list of floats."""
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1, 0.2, 0.3, 0.4]

        mock_response = MagicMock()
        mock_response.embeddings = [mock_embedding]

        llm_service._mock_client.models.embed_content.return_value = mock_response

        result = await llm_service.create_embedding("Test text")

        assert result == [0.1, 0.2, 0.3, 0.4]

    @pytest.mark.asyncio
    async def test_create_embedding_raises_on_error(self, llm_service):
        """create_embedding raises exception on API error."""
        llm_service._mock_client.models.embed_content.side_effect = Exception("Embedding Error")

        with pytest.raises(Exception) as exc:
            await llm_service.create_embedding("Test text")

        assert "Embedding Error" in str(exc.value)

    @pytest.mark.asyncio
    async def test_create_embeddings_batch_returns_list(self, llm_service):
        """create_embeddings_batch returns list of vectors."""
        mock_emb1 = MagicMock()
        mock_emb1.values = [0.1, 0.2]

        mock_emb2 = MagicMock()
        mock_emb2.values = [0.3, 0.4]

        mock_response = MagicMock()
        mock_response.embeddings = [mock_emb1, mock_emb2]

        llm_service._mock_client.models.embed_content.return_value = mock_response

        result = await llm_service.create_embeddings_batch(["Text 1", "Text 2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]
        assert result[1] == [0.3, 0.4]

    @pytest.mark.asyncio
    async def test_create_embeddings_batch_raises_on_error(self, llm_service):
        """create_embeddings_batch raises exception on API error."""
        llm_service._mock_client.models.embed_content.side_effect = Exception("Batch Error")

        with pytest.raises(Exception) as exc:
            await llm_service.create_embeddings_batch(["Text 1", "Text 2"])

        assert "Batch Error" in str(exc.value)
