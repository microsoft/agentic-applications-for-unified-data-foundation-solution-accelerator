"""
Unit tests for sample_user.py module with 95%+ coverage.
"""

from auth.sample_user import sample_user


class TestSampleUser:
    """Tests for sample_user dictionary."""

    def test_sample_user_exists(self):
        """Test that sample_user dictionary exists."""
        assert sample_user is not None

    def test_sample_user_is_dict(self):
        """Test that sample_user is a dictionary."""
        assert isinstance(sample_user, dict)

    def test_sample_user_not_empty(self):
        """Test that sample_user is not empty."""
        assert len(sample_user) > 0

    def test_has_principal_id(self):
        """Test that sample_user contains X-Ms-Client-Principal-Id."""
        assert "X-Ms-Client-Principal-Id" in sample_user

    def test_has_principal_name(self):
        """Test that sample_user contains X-Ms-Client-Principal-Name."""
        assert "X-Ms-Client-Principal-Name" in sample_user

    def test_has_principal_idp(self):
        """Test that sample_user contains X-Ms-Client-Principal-Idp."""
        assert "X-Ms-Client-Principal-Idp" in sample_user

    def test_has_token_aad_id_token(self):
        """Test that sample_user contains X-Ms-Token-Aad-Id-Token."""
        assert "X-Ms-Token-Aad-Id-Token" in sample_user

    def test_has_client_principal(self):
        """Test that sample_user contains X-Ms-Client-Principal."""
        assert "X-Ms-Client-Principal" in sample_user

    def test_principal_id_format(self):
        """Test that principal ID is in UUID format."""
        principal_id = sample_user.get("X-Ms-Client-Principal-Id")
        assert principal_id is not None
        
        # Check UUID format (8-4-4-4-12)
        parts = principal_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_principal_name_has_email(self):
        """Test that principal name contains an email address."""
        name = sample_user.get("X-Ms-Client-Principal-Name")
        assert name is not None
        assert "@" in name
        assert "." in name

    def test_idp_is_aad(self):
        """Test that identity provider is AAD."""
        idp = sample_user.get("X-Ms-Client-Principal-Idp")
        assert idp == "aad"

    def test_has_accept_header(self):
        """Test that sample_user includes Accept header."""
        assert "Accept" in sample_user
        assert sample_user["Accept"] == "*/*"

    def test_has_content_type(self):
        """Test that sample_user includes Content-Type header."""
        assert "Content-Type" in sample_user
        assert sample_user["Content-Type"] == "application/json"

    def test_has_user_agent(self):
        """Test that sample_user includes User-Agent header."""
        assert "User-Agent" in sample_user
        assert len(sample_user["User-Agent"]) > 0

    def test_has_host(self):
        """Test that sample_user includes Host header."""
        assert "Host" in sample_user

    def test_host_is_azure(self):
        """Test that host is an Azure App Service."""
        host = sample_user.get("Host")
        assert "azurewebsites.net" in host

    def test_has_security_headers(self):
        """Test that sample_user includes security-related headers."""
        security_headers = [
            "Sec-Fetch-Dest",
            "Sec-Fetch-Mode",
            "Sec-Fetch-Site",
        ]
        
        for header in security_headers:
            assert header in sample_user, f"Missing security header: {header}"

    def test_has_accept_encoding(self):
        """Test that sample_user includes Accept-Encoding header."""
        assert "Accept-Encoding" in sample_user

    def test_has_accept_language(self):
        """Test that sample_user includes Accept-Language header."""
        assert "Accept-Language" in sample_user

    def test_has_client_ip(self):
        """Test that sample_user includes Client-Ip header."""
        assert "Client-Ip" in sample_user

    def test_has_content_length(self):
        """Test that sample_user includes Content-Length header."""
        assert "Content-Length" in sample_user

    def test_has_cookie(self):
        """Test that sample_user includes Cookie header."""
        assert "Cookie" in sample_user

    def test_cookie_has_auth_session(self):
        """Test that Cookie contains AppServiceAuthSession."""
        cookie = sample_user.get("Cookie")
        assert "AppServiceAuthSession" in cookie

    def test_has_origin(self):
        """Test that sample_user includes Origin header."""
        assert "Origin" in sample_user

    def test_origin_is_https(self):
        """Test that Origin uses HTTPS."""
        origin = sample_user.get("Origin")
        assert origin.startswith("https://")

    def test_has_referer(self):
        """Test that sample_user includes Referer header."""
        assert "Referer" in sample_user

    def test_has_sec_ch_ua(self):
        """Test that sample_user includes Sec-Ch-Ua header."""
        assert "Sec-Ch-Ua" in sample_user

    def test_has_sec_ch_ua_mobile(self):
        """Test that sample_user includes Sec-Ch-Ua-Mobile header."""
        assert "Sec-Ch-Ua-Mobile" in sample_user

    def test_has_sec_ch_ua_platform(self):
        """Test that sample_user includes Sec-Ch-Ua-Platform header."""
        assert "Sec-Ch-Ua-Platform" in sample_user

    def test_has_traceparent(self):
        """Test that sample_user includes Traceparent header."""
        assert "Traceparent" in sample_user

    def test_has_x_azure_headers(self):
        """Test that sample_user includes Azure-specific headers."""
        azure_headers = [
            "X-Appservice-Proto",
            "X-Arr-Log-Id",
            "X-Arr-Ssl",
            "X-Client-Ip",
            "X-Client-Port",
            "X-Forwarded-For",
            "X-Forwarded-Proto",
            "X-Forwarded-Tlsversion",
        ]
        
        for header in azure_headers:
            assert header in sample_user, f"Missing Azure header: {header}"

    def test_has_x_original_url(self):
        """Test that sample_user includes X-Original-Url header."""
        assert "X-Original-Url" in sample_user

    def test_has_disguised_host(self):
        """Test that sample_user includes Disguised-Host header."""
        assert "Disguised-Host" in sample_user

    def test_has_was_default_hostname(self):
        """Test that sample_user includes Was-Default-Hostname header."""
        assert "Was-Default-Hostname" in sample_user

    def test_has_x_site_deployment_id(self):
        """Test that sample_user includes X-Site-Deployment-Id header."""
        assert "X-Site-Deployment-Id" in sample_user

    def test_has_x_waws_unencoded_url(self):
        """Test that sample_user includes X-Waws-Unencoded-Url header."""
        assert "X-Waws-Unencoded-Url" in sample_user

    def test_has_max_forwards(self):
        """Test that sample_user includes Max-Forwards header."""
        assert "Max-Forwards" in sample_user

    def test_x_forwarded_proto_is_https(self):
        """Test that X-Forwarded-Proto is HTTPS."""
        proto = sample_user.get("X-Forwarded-Proto")
        assert proto == "https"

    def test_x_appservice_proto_is_https(self):
        """Test that X-Appservice-Proto is HTTPS."""
        proto = sample_user.get("X-Appservice-Proto")
        assert proto == "https"

    def test_all_values_are_strings(self):
        """Test that all values in sample_user are strings."""
        for key, value in sample_user.items():
            assert isinstance(value, str), f"Value for {key} is not a string: {type(value)}"

    def test_all_keys_are_strings(self):
        """Test that all keys in sample_user are strings."""
        for key in sample_user.keys():
            assert isinstance(key, str), f"Key {key} is not a string: {type(key)}"

    def test_no_none_values(self):
        """Test that sample_user has no None values."""
        for key, value in sample_user.items():
            assert value is not None, f"Value for {key} is None"

    def test_no_empty_values(self):
        """Test that sample_user has no empty string values."""
        for key, value in sample_user.items():
            assert len(value) > 0, f"Value for {key} is empty"

    def test_sample_user_is_mutable(self):
        """Test that sample_user can be used as a mutable dictionary in tests."""
        # Should be able to create a copy
        copy = sample_user.copy()
        assert copy == sample_user
        assert copy is not sample_user

    def test_can_access_with_get(self):
        """Test that sample_user supports .get() method."""
        value = sample_user.get("Host")
        assert value is not None

    def test_get_with_default(self):
        """Test that sample_user.get() supports default values."""
        value = sample_user.get("NonExistentHeader", "default")
        assert value == "default"

    def test_headers_case_preserved(self):
        """Test that header case is preserved (not normalized)."""
        # Check that we have mixed case headers
        has_capitalized = any(key[0].isupper() for key in sample_user.keys() if key)
        assert has_capitalized

    def test_can_iterate_over_items(self):
        """Test that we can iterate over sample_user items."""
        count = 0
        for key, value in sample_user.items():
            assert key is not None
            assert value is not None
            count += 1
        assert count > 0

    def test_len_returns_positive(self):
        """Test that len(sample_user) returns a positive number."""
        length = len(sample_user)
        assert length > 30  # Should have many headers

    def test_principal_id_is_placeholder(self):
        """Test that the principal ID is a placeholder UUID."""
        principal_id = sample_user.get("X-Ms-Client-Principal-Id")
        # Check if it's a valid UUID format
        assert "-" in principal_id
        parts = principal_id.split("-")
        assert len(parts) == 5
